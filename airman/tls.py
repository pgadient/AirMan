"""HTTPS certificates for the web page.

Phones nowadays insist on HTTPS. Without a public domain we can not get a
publicly trusted certificate, so AirMan creates a small local certificate
authority (CA) and signs its own server certificate with it.

The CA is restricted with X.509 name constraints: it can only vouch for private
IP addresses, "localhost" and this computer's own name. Even if its key leaked,
it could not be used to impersonate any real website on a phone that trusts it.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import logging
import os
import socket
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .config import restrict_to_user

_LOGGER = logging.getLogger(__name__)

CA_DAYS = 3650
LEAF_DAYS = 397  # Apple rejects server certificates valid for longer
RENEW_BEFORE = dt.timedelta(days=30)

PERMITTED_NETWORKS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "fc00::/7",
    "fe80::/10",
    "::1/128",
]


def local_names() -> list[str]:
    # Not the bare host name: a single label like "dev" could also be a top-level domain.
    host = socket.gethostname().lower()
    names = {"localhost", f"{host}.local"}
    return sorted(n for n in names if n and all(c.isalnum() or c in "-." for c in n))


def local_addresses() -> list[str]:
    addresses = {"127.0.0.1"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    return sorted(addresses)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _write_private(path: Path, data: bytes) -> None:
    """Write a secret so that only the current user can read it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    restrict_to_user(tmp)
    os.replace(tmp, path)


def _key_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def _load_or_create_ca(tls_dir: Path) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key_file, cert_file = tls_dir / "ca-key.pem", tls_dir / "ca.pem"
    if key_file.exists() and cert_file.exists():
        key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
        if cert.not_valid_after_utc - RENEW_BEFORE > _now() and isinstance(
                key, ec.EllipticCurvePrivateKey):
            return key, cert
        _LOGGER.warning("Local CA expires soon, creating a new one (reinstall it on phones)")

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"AirMan local CA ({socket.gethostname()})"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AirMan"),
    ])
    hosts = [x509.DNSName(n) for n in local_names()]
    networks = [x509.IPAddress(ipaddress.ip_network(n)) for n in PERMITTED_NETWORKS]
    now = _now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        # Only for web servers: a leaked key could not sign programs or e-mail certificates.
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.NameConstraints(permitted_subtrees=hosts + networks,
                                            excluded_subtrees=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    _write_private(key_file, _key_pem(key))
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # A new CA invalidates the old server certificate.
    (tls_dir / "server.pem").unlink(missing_ok=True)
    return key, cert


def _leaf_matches(cert_file: Path, names: list[str], ips: list[str]) -> bool:
    try:
        cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except (OSError, ValueError, x509.ExtensionNotFound):
        return False
    have_names = set(san.get_values_for_type(x509.DNSName))
    have_ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    return (cert.not_valid_after_utc - RENEW_BEFORE > _now()
            and set(names) <= have_names and set(ips) <= have_ips)


def ensure_certificates(tls_dir: Path) -> tuple[Path, Path, Path]:
    """Return (server certificate chain, server key, CA certificate), creating them if needed."""
    ca_key, ca_cert = _load_or_create_ca(tls_dir)
    cert_file, key_file = tls_dir / "server.pem", tls_dir / "server-key.pem"
    names = local_names()
    ips = [ip for ip in local_addresses()
           if any(ipaddress.ip_address(ip) in ipaddress.ip_network(n) for n in PERMITTED_NETWORKS)]
    if key_file.exists() and _leaf_matches(cert_file, names, ips):
        return cert_file, key_file, tls_dir / "ca.pem"

    _LOGGER.info("Creating HTTPS certificate for %s", ", ".join(names + ips))
    key = ec.generate_private_key(ec.SECP256R1())
    now = _now()
    san = [x509.DNSName(n) for n in names] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=LEAF_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                       critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write_private(key_file, _key_pem(key))
    chain = cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(
        serialization.Encoding.PEM)
    cert_file.write_bytes(chain)
    return cert_file, key_file, tls_dir / "ca.pem"


def server_context(cert_file: Path, key_file: Path) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_file, key_file)
    return context
