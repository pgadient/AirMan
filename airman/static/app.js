"use strict";

// Older Safari (iPod, old iPads before iOS 14) lacks replaceChildren.
if (!Element.prototype.replaceChildren) {
  Element.prototype.replaceChildren = function replaceChildren(...nodes) {
    while (this.firstChild) this.removeChild(this.firstChild);
    this.append(...nodes);
  };
}

// ----- texts -----------------------------------------------------------------

const TEXTS = {
  de: {
    lowDisk: "⚠ Nur noch {g} GB frei auf dem AirMan-Server. Neue Downloads und Uploads könnten fehlschlagen.",
    downloading: "Lädt herunter … {p}{eta}",
    timeLeft: " · noch {t}",
    files: "Dateien",
    upload: "⬆ Hochladen",
    uploading: "Hochladen … {p} %",
    uploaded: "{n} Datei(en) hochgeladen",
    uploadFailed: "Hochladen fehlgeschlagen: {e}",
    filesEmpty: "Noch keine Dateien. Lade Musik hoch oder spiele etwas von YouTube.",
    deleteFile: "Löschen",
    deleteConfirm: "„{t}“ löschen?",
    offlineBadge: "Offline",
    modeSimple: "Einfach",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Zur Playlist hinzufügen auf",
    addedTo: "Zur Playlist von {s} hinzugefügt",
    clearPlaylist: "Playlist leeren",
    emptyPlaylist: "Die Playlist ist leer. Oben suchen und hinzufügen.",
    moveUp: "Nach oben",
    moveDown: "Nach unten",
    removeSong: "Entfernen",
    password: "Passwort",
    login: "Anmelden",
    wrongPassword: "Falsches Passwort",
    installCert: "Zertifikat installieren (optional, gegen Warnungen)",
    locked: "Zu viele Versuche. Bitte {s} s warten.",
    searchPlaceholder: "Suchen oder Link einfügen",
    close: "Schliessen",
    noSpeakers: "Keine Lautsprecher gefunden. Sind sie im gleichen Netzwerk?",
    rescan: "Lautsprecher suchen",
    logout: "Abmelden",
    playOn: "Abspielen auf",
    cancel: "Abbrechen",
    continue: "Abspielen",
    pause: "Pause",
    restart: "Neustart",
    stop: "Stopp",
    repeatOne: "🔂 Song",
    repeatAll: "🔁 Alle",
    repeatOff: "→ Einmal",
    sleepOff: "🌙 Aus",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Zuletzt gespielt",
    idle: "Bereit",
    nothingYet: "Noch nichts gespielt. Oben suchen.",
    lastPlayed: "Zuletzt: {t}",
    loading: "Lädt …",
    interrupted: "Von einem anderen Gerät übernommen",
    offline: "Nicht erreichbar",
    results: "{n} Treffer",
    searching: "Suche …",
    noResults: "Nichts gefunden",
    live: "Live",
    started: "Läuft auf {s}",
    error: "Fehler: {e}",
    scanning: "Suche Lautsprecher …",
    stereoPair: "Stereopaar",
    stereo: "Stereo-Einstellungen",
    testTone: "🔊 L/R-Test",
    testHint: "Tiefer Ton = links, hoher Ton = rechts.",
    whichLeft: "Welcher steht links?",
    balance: "Balance",
    resetCentre: "Auf Mitte zurücksetzen",
    splitPair: "Einzeln steuern",
    joinPair: "Als Stereopaar nutzen ({p})",
    coffee: "Buy me a coffee",
    reportBug: "Fehler melden",
    reportIssue: "🐞 Issue auf GitHub öffnen",
    copyLogs: "📋 Logs kopieren",
    copied: "Logs kopiert. Im Issue einfügen.",
    toDay: "Tagmodus",
    toNight: "Nachtmodus",
    groupOn: "Gruppe {g}: spielt synchron mit den anderen Lautsprechern der Gruppe",
    groupName: "Gruppe {g}",
    groupOff: "Keine Gruppe – tippen, um diesen Lautsprecher einer Gruppe zuzuordnen",
    startFailed: "AirMan konnte nicht starten",
    reload: "Neu laden",
    pairHint: "Dieses Apple TV muss einmal gekoppelt werden. Danach zeigt es eine PIN auf dem Fernseher.",
    pair: "Koppeln",
    pairConfirm: "OK",
    pairDone: "Gekoppelt",
    switchMascot: "Mond oder Note anzeigen",
    logsTitle: "Fehler melden",
    logsMail: "✉️ Per E-Mail an {e}",
    logsMailNoAddress: "✉️ Per E-Mail",
    logsShare: "📄 Als Datei teilen",
    logsHint: "Beschreibe auf GitHub, was passiert ist, und füge die Logs ein – oder schick sie per E-Mail. Die Logs enthalten keine Passwörter.",
    logsTruncated: "(gekürzt, ganze Logs: \"Als Datei teilen\")",
    language: "Sprache",
    resumeAt: "Ab Position: {t}",
  },
  en: {
    lowDisk: "⚠ Only {g} GB free on the AirMan server. New downloads and uploads may fail.",
    downloading: "Downloading … {p}{eta}",
    timeLeft: " · {t} left",
    files: "Files",
    upload: "⬆ Upload",
    uploading: "Uploading … {p} %",
    uploaded: "{n} file(s) uploaded",
    uploadFailed: "Upload failed: {e}",
    filesEmpty: "No files yet. Upload music or play something from YouTube.",
    deleteFile: "Delete",
    deleteConfirm: "Delete “{t}”?",
    offlineBadge: "Offline",
    modeSimple: "Simple",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Add to the playlist on",
    addedTo: "Added to the playlist of {s}",
    clearPlaylist: "Clear playlist",
    emptyPlaylist: "The playlist is empty. Search above and add songs.",
    moveUp: "Move up",
    moveDown: "Move down",
    removeSong: "Remove",
    password: "Password",
    login: "Log in",
    wrongPassword: "Wrong password",
    installCert: "Install certificate (optional, avoids warnings)",
    locked: "Too many attempts. Please wait {s} s.",
    searchPlaceholder: "Search or paste a link",
    close: "Close",
    noSpeakers: "No speakers found. Are they on the same network?",
    rescan: "Find speakers",
    logout: "Log out",
    playOn: "Play on",
    cancel: "Cancel",
    continue: "Play",
    pause: "Pause",
    restart: "Restart",
    stop: "Stop",
    repeatOne: "🔂 Song",
    repeatAll: "🔁 All",
    repeatOff: "→ Once",
    sleepOff: "🌙 Off",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Recently played",
    idle: "Ready",
    nothingYet: "Nothing played yet. Search above.",
    lastPlayed: "Last: {t}",
    loading: "Loading …",
    interrupted: "Taken over by another device",
    offline: "Not reachable",
    results: "{n} results",
    searching: "Searching …",
    noResults: "Nothing found",
    live: "Live",
    started: "Playing on {s}",
    error: "Error: {e}",
    scanning: "Looking for speakers …",
    stereoPair: "Stereo pair",
    stereo: "Stereo settings",
    testTone: "🔊 L/R test",
    testHint: "Low tone = left, high tone = right.",
    whichLeft: "Which one is on the left?",
    balance: "Balance",
    resetCentre: "Reset to centre",
    splitPair: "Control separately",
    joinPair: "Use as stereo pair ({p})",
    coffee: "Buy me a coffee",
    reportBug: "Report bug",
    reportIssue: "🐞 Open an issue on GitHub",
    copyLogs: "📋 Copy logs",
    copied: "Logs copied. Paste them into the issue.",
    toDay: "Day mode",
    toNight: "Night mode",
    groupOn: "Group {g}: plays in sync with the other speakers of the group",
    groupName: "Group {g}",
    groupOff: "No group – tap to put this speaker into a group",
    startFailed: "AirMan could not start",
    reload: "Reload",
    pairHint: "This Apple TV must be paired once. It then shows a PIN on the TV.",
    pair: "Pair",
    pairConfirm: "OK",
    pairDone: "Paired",
    switchMascot: "Show moon or note",
    logsTitle: "Report a bug",
    logsMail: "✉️ Email to {e}",
    logsMailNoAddress: "✉️ Email",
    logsShare: "📄 Share as file",
    logsHint: "Describe on GitHub what happened and paste the logs – or send them by email. Logs contain no passwords.",
    logsTruncated: "(shortened, full logs: \"Share as file\")",
    language: "Language",
    resumeAt: "From position: {t}",
  },
  gsw: {
    lowDisk: "⚠ Nume no {g} GB frei uf em AirMan-Server. Neui Downloads und Uploads chönnted fehlschlah.",
    downloading: "Ladt abe … {p}{eta}",
    timeLeft: " · no {t}",
    files: "Dateie",
    upload: "⬆ Ufelade",
    uploading: "Ufelade … {p} %",
    uploaded: "{n} Datei(e) ufeglade",
    uploadFailed: "Ufelade het nöd klappt: {e}",
    filesEmpty: "No kei Dateie. Lad Musig ufe oder spil öppis vo YouTube.",
    deleteFile: "Lösche",
    deleteConfirm: "«{t}» lösche?",
    offlineBadge: "Offline",
    modeSimple: "Eifach",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Zur Playlist dezuetue uf",
    addedTo: "Zur Playlist vo {s} dezuetaa",
    clearPlaylist: "Playlist leere",
    emptyPlaylist: "D Playlist isch leer. Obe sueche und dezuetue.",
    moveUp: "Ufe",
    moveDown: "Abe",
    removeSong: "Entferne",
    password: "Passwort",
    login: "Aamälde",
    wrongPassword: "Falsches Passwort",
    installCert: "Zertifikat installiere (optional, gäge Warnige)",
    locked: "Z vill Versüech. Bitte {s} s warte.",
    searchPlaceholder: "Sueche oder Link iifüege",
    close: "Zue",
    noSpeakers: "Kei Lutsprächer gfunde. Sind's im gliiche Netz?",
    rescan: "Lutsprächer sueche",
    logout: "Abmälde",
    playOn: "Abspile uf",
    cancel: "Abbräche",
    continue: "Abspile",
    pause: "Pause",
    restart: "Neustart",
    stop: "Stopp",
    repeatOne: "🔂 Lied",
    repeatAll: "🔁 Alli",
    repeatOff: "→ Eimal",
    sleepOff: "🌙 Us",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Zletscht gspilt",
    idle: "Parat",
    nothingYet: "No nüt gspilt. Obe sueche.",
    lastPlayed: "Zletscht: {t}",
    loading: "Ladt …",
    interrupted: "Vo eme andere Grät übernoh",
    offline: "Nöd erreichbar",
    results: "{n} Träffer",
    searching: "Sueche …",
    noResults: "Nüt gfunde",
    live: "Live",
    started: "Lauft uf {s}",
    error: "Fähler: {e}",
    scanning: "Suech Lutsprächer …",
    stereoPair: "Stereopaar",
    stereo: "Stereo-Iistellige",
    testTone: "🔊 L/R-Test",
    testHint: "Tüüfe Ton = links, hoche Ton = rächts.",
    whichLeft: "Wele stoht links?",
    balance: "Balance",
    resetCentre: "Uf d Mitti zruggsetze",
    splitPair: "Einzeln stüüre",
    joinPair: "Als Stereopaar bruuche ({p})",
    coffee: "Kafi spändiere",
    reportBug: "Fähler mälde",
    reportIssue: "🐞 Issue uf GitHub uftue",
    copyLogs: "📋 Logs kopiere",
    copied: "Logs kopiert. Im Issue iifüege.",
    toDay: "Tagmodus",
    toNight: "Nachtmodus",
    groupOn: "Gruppe {g}: spielt synchron mit de andere Luutsprächer vo de Gruppe",
    groupName: "Gruppe {g}",
    groupOff: "Kei Gruppe – tippe, zum de Luutsprächer ere Gruppe zuezordne",
    startFailed: "AirMan het nöd chönne starte",
    reload: "Neu lade",
    pairHint: "Das Apple TV muess eimal kopplet werde. Dänn zeigts e PIN uf em Fernseh.",
    pair: "Kopple",
    pairConfirm: "OK",
    pairDone: "Kopplet",
    switchMascot: "Mond oder Note zeige",
    logsTitle: "Fähler mälde",
    logsMail: "✉️ Per E-Mail a {e}",
    logsMailNoAddress: "✉️ Per E-Mail",
    logsShare: "📄 Als Datei teile",
    logsHint: "Beschriib uf GitHub, was passiert isch, und füeg d Logs ii – oder schick sie per E-Mail. D Logs händ kei Passwörter drin.",
    logsTruncated: "(kürzt, ganzi Logs: \"Als Datei teile\")",
    language: "Sprach",
    resumeAt: "Ab Position: {t}",
  },
  fr: {
    lowDisk: "⚠ Plus que {g} Go libres sur le serveur AirMan. Les nouveaux téléchargements et imports peuvent échouer.",
    downloading: "Téléchargement … {p}{eta}",
    timeLeft: " · encore {t}",
    files: "Fichiers",
    upload: "⬆ Importer",
    uploading: "Import … {p} %",
    uploaded: "{n} fichier(s) importé(s)",
    uploadFailed: "Échec de l'import : {e}",
    filesEmpty: "Pas encore de fichiers. Importez de la musique ou écoutez quelque chose sur YouTube.",
    deleteFile: "Supprimer",
    deleteConfirm: "Supprimer « {t} » ?",
    offlineBadge: "Hors ligne",
    modeSimple: "Simple",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Ajouter à la playlist de",
    addedTo: "Ajouté à la playlist de {s}",
    clearPlaylist: "Vider la playlist",
    emptyPlaylist: "La playlist est vide. Cherchez en haut et ajoutez des titres.",
    moveUp: "Monter",
    moveDown: "Descendre",
    removeSong: "Retirer",
    password: "Mot de passe",
    login: "Se connecter",
    wrongPassword: "Mot de passe incorrect",
    installCert: "Installer le certificat (facultatif, évite les avertissements)",
    locked: "Trop de tentatives. Veuillez patienter {s} s.",
    searchPlaceholder: "Rechercher ou coller un lien",
    close: "Fermer",
    noSpeakers: "Aucune enceinte trouvée. Sont-elles sur le même réseau ?",
    rescan: "Chercher les enceintes",
    logout: "Se déconnecter",
    playOn: "Lire sur",
    cancel: "Annuler",
    continue: "Lecture",
    pause: "Pause",
    restart: "Recommencer",
    stop: "Arrêt",
    repeatOne: "🔂 Titre",
    repeatAll: "🔁 Tout",
    repeatOff: "→ Une fois",
    sleepOff: "🌙 Non",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Écouté récemment",
    idle: "Prêt",
    nothingYet: "Rien écouté pour l'instant. Cherchez en haut.",
    lastPlayed: "Dernier : {t}",
    loading: "Chargement …",
    interrupted: "Repris par un autre appareil",
    offline: "Injoignable",
    results: "{n} résultats",
    searching: "Recherche …",
    noResults: "Aucun résultat",
    live: "En direct",
    started: "Lecture sur {s}",
    error: "Erreur : {e}",
    scanning: "Recherche des enceintes …",
    stereoPair: "Paire stéréo",
    stereo: "Réglages stéréo",
    testTone: "🔊 Test G/D",
    testHint: "Son grave = gauche, son aigu = droite.",
    whichLeft: "Laquelle est à gauche ?",
    balance: "Balance",
    resetCentre: "Remettre au centre",
    splitPair: "Contrôler séparément",
    joinPair: "Utiliser en paire stéréo ({p})",
    coffee: "Offrir un café",
    reportBug: "Signaler un bug",
    reportIssue: "🐞 Ouvrir un ticket sur GitHub",
    copyLogs: "📋 Copier les logs",
    copied: "Logs copiés. Collez-les dans le ticket.",
    toDay: "Mode jour",
    toNight: "Mode nuit",
    groupOn: "Groupe {g} : joue en synchronisation avec les autres enceintes du groupe",
    groupName: "Groupe {g}",
    groupOff: "Aucun groupe – touchez pour ajouter cette enceinte à un groupe",
    startFailed: "AirMan n'a pas pu démarrer",
    reload: "Recharger",
    pairHint: "Cet Apple TV doit être jumelé une fois. Il affiche alors un code PIN sur le téléviseur.",
    pair: "Jumeler",
    pairConfirm: "OK",
    pairDone: "Jumelé",
    switchMascot: "Afficher la lune ou la note",
    logsTitle: "Signaler un bug",
    logsMail: "✉️ Par e-mail à {e}",
    logsMailNoAddress: "✉️ Par e-mail",
    logsShare: "📄 Partager le fichier",
    logsHint: "Décrivez sur GitHub ce qui s'est passé et collez les logs – ou envoyez-les par e-mail. Les logs ne contiennent aucun mot de passe.",
    logsTruncated: "(raccourci, logs complets : « Partager le fichier »)",
    language: "Langue",
    resumeAt: "À partir de : {t}",
  },
  it: {
    lowDisk: "⚠ Solo {g} GB liberi sul server di AirMan. Nuovi download e caricamenti potrebbero non riuscire.",
    downloading: "Download … {p}{eta}",
    timeLeft: " · ancora {t}",
    files: "File",
    upload: "⬆ Carica",
    uploading: "Caricamento … {p} %",
    uploaded: "{n} file caricati",
    uploadFailed: "Caricamento non riuscito: {e}",
    filesEmpty: "Ancora nessun file. Carica della musica o ascolta qualcosa da YouTube.",
    deleteFile: "Elimina",
    deleteConfirm: "Eliminare «{t}»?",
    offlineBadge: "Offline",
    modeSimple: "Semplice",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Aggiungi alla playlist di",
    addedTo: "Aggiunto alla playlist di {s}",
    clearPlaylist: "Svuota playlist",
    emptyPlaylist: "La playlist è vuota. Cerca qui sopra e aggiungi brani.",
    moveUp: "Sposta su",
    moveDown: "Sposta giù",
    removeSong: "Rimuovi",
    password: "Password",
    login: "Accedi",
    wrongPassword: "Password errata",
    installCert: "Installa il certificato (facoltativo, evita gli avvisi)",
    locked: "Troppi tentativi. Attendi {s} s.",
    searchPlaceholder: "Cerca o incolla un link",
    close: "Chiudi",
    noSpeakers: "Nessun altoparlante trovato. Sono nella stessa rete?",
    rescan: "Cerca altoparlanti",
    logout: "Esci",
    playOn: "Riproduci su",
    cancel: "Annulla",
    continue: "Riproduci",
    pause: "Pausa",
    restart: "Ricomincia",
    stop: "Stop",
    repeatOne: "🔂 Brano",
    repeatAll: "🔁 Tutti",
    repeatOff: "→ Una volta",
    sleepOff: "🌙 No",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Ascoltati di recente",
    idle: "Pronto",
    nothingYet: "Ancora niente. Cerca qui sopra.",
    lastPlayed: "Ultimo: {t}",
    loading: "Caricamento …",
    interrupted: "Preso da un altro dispositivo",
    offline: "Non raggiungibile",
    results: "{n} risultati",
    searching: "Ricerca …",
    noResults: "Nessun risultato",
    live: "Live",
    started: "In riproduzione su {s}",
    error: "Errore: {e}",
    scanning: "Cerco gli altoparlanti …",
    stereoPair: "Coppia stereo",
    stereo: "Impostazioni stereo",
    testTone: "🔊 Test S/D",
    testHint: "Tono basso = sinistra, tono alto = destra.",
    whichLeft: "Quale sta a sinistra?",
    balance: "Bilanciamento",
    resetCentre: "Riporta al centro",
    splitPair: "Controlla separatamente",
    joinPair: "Usa come coppia stereo ({p})",
    coffee: "Offrimi un caffè",
    reportBug: "Segnala un bug",
    reportIssue: "🐞 Apri una issue su GitHub",
    copyLogs: "📋 Copia i log",
    copied: "Log copiati. Incollali nella issue.",
    toDay: "Modalità giorno",
    toNight: "Modalità notte",
    groupOn: "Gruppo {g}: suona in sincrono con gli altri altoparlanti del gruppo",
    groupName: "Gruppo {g}",
    groupOff: "Nessun gruppo – tocca per aggiungere questo altoparlante a un gruppo",
    startFailed: "AirMan non è riuscito ad avviarsi",
    reload: "Ricarica",
    pairHint: "Questa Apple TV va abbinata una volta. Mostrerà poi un PIN sul televisore.",
    pair: "Abbina",
    pairConfirm: "OK",
    pairDone: "Abbinata",
    switchMascot: "Mostra luna o nota",
    logsTitle: "Segnala un bug",
    logsMail: "✉️ Via e-mail a {e}",
    logsMailNoAddress: "✉️ Via e-mail",
    logsShare: "📄 Condividi come file",
    logsHint: "Descrivi su GitHub cosa è successo e incolla i log – oppure inviali via e-mail. I log non contengono password.",
    logsTruncated: "(accorciato, log completi: \"Condividi come file\")",
    language: "Lingua",
    resumeAt: "Dalla posizione: {t}",
  },
  es: {
    lowDisk: "⚠ Solo quedan {g} GB libres en el servidor de AirMan. Las nuevas descargas y subidas podrían fallar.",
    downloading: "Descargando … {p}{eta}",
    timeLeft: " · faltan {t}",
    files: "Archivos",
    upload: "⬆ Subir",
    uploading: "Subiendo … {p} %",
    uploaded: "{n} archivo(s) subido(s)",
    uploadFailed: "Error al subir: {e}",
    filesEmpty: "Aún no hay archivos. Sube música o escucha algo de YouTube.",
    deleteFile: "Eliminar",
    deleteConfirm: "¿Eliminar «{t}»?",
    offlineBadge: "Sin conexión",
    modeSimple: "Sencillo",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Añadir a la playlist de",
    addedTo: "Añadido a la playlist de {s}",
    clearPlaylist: "Vaciar playlist",
    emptyPlaylist: "La playlist está vacía. Busca arriba y añade canciones.",
    moveUp: "Subir",
    moveDown: "Bajar",
    removeSong: "Quitar",
    password: "Contraseña",
    login: "Entrar",
    wrongPassword: "Contraseña incorrecta",
    installCert: "Instalar certificado (opcional, evita avisos)",
    locked: "Demasiados intentos. Espera {s} s.",
    searchPlaceholder: "Buscar o pegar un enlace",
    close: "Cerrar",
    noSpeakers: "No se encontraron altavoces. ¿Están en la misma red?",
    rescan: "Buscar altavoces",
    logout: "Salir",
    playOn: "Reproducir en",
    cancel: "Cancelar",
    continue: "Reproducir",
    pause: "Pausa",
    restart: "Reiniciar",
    stop: "Parar",
    repeatOne: "🔂 Canción",
    repeatAll: "🔁 Todas",
    repeatOff: "→ Una vez",
    sleepOff: "🌙 No",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Escuchado recientemente",
    idle: "Listo",
    nothingYet: "Aún nada. Busca arriba.",
    lastPlayed: "Último: {t}",
    loading: "Cargando …",
    interrupted: "Tomado por otro dispositivo",
    offline: "No disponible",
    results: "{n} resultados",
    searching: "Buscando …",
    noResults: "Sin resultados",
    live: "En directo",
    started: "Sonando en {s}",
    error: "Error: {e}",
    scanning: "Buscando altavoces …",
    stereoPair: "Par estéreo",
    stereo: "Ajustes estéreo",
    testTone: "🔊 Prueba I/D",
    testHint: "Tono grave = izquierda, tono agudo = derecha.",
    whichLeft: "¿Cuál está a la izquierda?",
    balance: "Balance",
    resetCentre: "Volver al centro",
    splitPair: "Controlar por separado",
    joinPair: "Usar como par estéreo ({p})",
    coffee: "Invítame a un café",
    reportBug: "Informar de un error",
    reportIssue: "🐞 Abrir un issue en GitHub",
    copyLogs: "📋 Copiar logs",
    copied: "Logs copiados. Pégalos en el issue.",
    toDay: "Modo día",
    toNight: "Modo noche",
    groupOn: "Grupo {g}: suena sincronizado con los demás altavoces del grupo",
    groupName: "Grupo {g}",
    groupOff: "Sin grupo – toca para añadir este altavoz a un grupo",
    startFailed: "AirMan no pudo iniciarse",
    reload: "Recargar",
    pairHint: "Este Apple TV debe vincularse una vez. Después mostrará un PIN en el televisor.",
    pair: "Vincular",
    pairConfirm: "OK",
    pairDone: "Vinculado",
    switchMascot: "Mostrar luna o nota",
    logsTitle: "Informar de un error",
    logsMail: "✉️ Por e-mail a {e}",
    logsMailNoAddress: "✉️ Por e-mail",
    logsShare: "📄 Compartir como archivo",
    logsHint: "Describe en GitHub qué pasó y pega los logs – o envíalos por e-mail. Los logs no contienen contraseñas.",
    logsTruncated: "(acortado, logs completos: \"Compartir como archivo\")",
    language: "Idioma",
    resumeAt: "Desde la posición: {t}",
  },
  pt: {
    lowDisk: "⚠ Apenas {g} GB livres no servidor do AirMan. Novas transferências e carregamentos podem falhar.",
    downloading: "A transferir … {p}{eta}",
    timeLeft: " · faltam {t}",
    files: "Ficheiros",
    upload: "⬆ Carregar",
    uploading: "A carregar … {p} %",
    uploaded: "{n} ficheiro(s) carregado(s)",
    uploadFailed: "Falha ao carregar: {e}",
    filesEmpty: "Ainda não há ficheiros. Carregue música ou ouça algo do YouTube.",
    deleteFile: "Apagar",
    deleteConfirm: "Apagar «{t}»?",
    offlineBadge: "Offline",
    modeSimple: "Simples",
    modePlaylist: "Playlist",
    playlist: "Playlist ({n})",
    addTo: "Adicionar à playlist de",
    addedTo: "Adicionado à playlist de {s}",
    clearPlaylist: "Limpar playlist",
    emptyPlaylist: "A playlist está vazia. Pesquise acima e adicione músicas.",
    moveUp: "Subir",
    moveDown: "Descer",
    removeSong: "Remover",
    password: "Palavra-passe",
    login: "Entrar",
    wrongPassword: "Palavra-passe errada",
    installCert: "Instalar certificado (opcional, evita avisos)",
    locked: "Demasiadas tentativas. Aguarde {s} s.",
    searchPlaceholder: "Pesquisar ou colar um link",
    close: "Fechar",
    noSpeakers: "Nenhuma coluna encontrada. Estão na mesma rede?",
    rescan: "Procurar colunas",
    logout: "Sair",
    playOn: "Reproduzir em",
    cancel: "Cancelar",
    continue: "Reproduzir",
    pause: "Pausa",
    restart: "Recomeçar",
    stop: "Parar",
    repeatOne: "🔂 Música",
    repeatAll: "🔁 Todas",
    repeatOff: "→ Uma vez",
    sleepOff: "🌙 Não",
    sleepOn: "🌙 {m}",
    previous: "⏮",
    next: "⏭",
    history: "Ouvido recentemente",
    idle: "Pronto",
    nothingYet: "Ainda nada. Pesquise acima.",
    lastPlayed: "Último: {t}",
    loading: "A carregar …",
    interrupted: "Assumido por outro dispositivo",
    offline: "Indisponível",
    results: "{n} resultados",
    searching: "A pesquisar …",
    noResults: "Nada encontrado",
    live: "Ao vivo",
    started: "A tocar em {s}",
    error: "Erro: {e}",
    scanning: "A procurar colunas …",
    stereoPair: "Par estéreo",
    stereo: "Definições estéreo",
    testTone: "🔊 Teste E/D",
    testHint: "Som grave = esquerda, som agudo = direita.",
    whichLeft: "Qual está à esquerda?",
    balance: "Balanço",
    resetCentre: "Repor ao centro",
    splitPair: "Controlar separadamente",
    joinPair: "Usar como par estéreo ({p})",
    coffee: "Paga-me um café",
    reportBug: "Reportar erro",
    reportIssue: "🐞 Abrir uma issue no GitHub",
    copyLogs: "📋 Copiar logs",
    copied: "Logs copiados. Cole-os na issue.",
    toDay: "Modo dia",
    toNight: "Modo noite",
    groupOn: "Grupo {g}: toca em sincronia com as outras colunas do grupo",
    groupName: "Grupo {g}",
    groupOff: "Sem grupo – toque para adicionar esta coluna a um grupo",
    startFailed: "Não foi possível iniciar o AirMan",
    reload: "Recarregar",
    pairHint: "Esta Apple TV tem de ser emparelhada uma vez. Depois mostra um PIN na televisão.",
    pair: "Emparelhar",
    pairConfirm: "OK",
    pairDone: "Emparelhada",
    switchMascot: "Mostrar lua ou nota",
    logsTitle: "Reportar erro",
    logsMail: "✉️ Por e-mail para {e}",
    logsMailNoAddress: "✉️ Por e-mail",
    logsShare: "📄 Partilhar como ficheiro",
    logsHint: "Descreva no GitHub o que aconteceu e cole os logs – ou envie-os por e-mail. Os logs não contêm palavras-passe.",
    logsTruncated: "(encurtado, logs completos: \"Partilhar como ficheiro\")",
    language: "Idioma",
    resumeAt: "A partir de: {t}",
  },
};

// Languages in the picker; "system" follows the device.
const LANGUAGES = [
  ["system", "System"],
  ["en", "English"],
  ["de", "Deutsch"],
  ["gsw", "Schwiizerdütsch"],
  ["fr", "Français"],
  ["it", "Italiano"],
  ["es", "Español"],
  ["pt", "Português"],
];

function storedLanguage() {
  try { return localStorage.getItem("airman.lang") || "system"; } catch { return "system"; }
}

function systemLanguage() {
  for (const tag of navigator.languages || [navigator.language || "en"]) {
    const code = tag.toLowerCase().split("-")[0];
    if (code in TEXTS) return code;
  }
  return "en";
}

const LANG_CHOICE = storedLanguage();
const LANG = LANG_CHOICE in TEXTS ? LANG_CHOICE : systemLanguage();

function t(key, vars = {}) {
  const text = [TEXTS[LANG][key], TEXTS.en[key], key].find((v) => v != null);
  return text.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] != null ? vars[name] : ""));
}

const SLEEP_STEPS = [0, 15, 30, 45, 60, 90, 120, 150, 180, 240];
const REPEAT_NEXT = { one: "all", all: "off", off: "one" };
const REPEAT_LABEL = { one: "repeatOne", all: "repeatAll", off: "repeatOff" };

// ----- tiny DOM helper (textContent only, never innerHTML) ---------------------

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value !== false && value != null) el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child != null) el.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return el;
}

const $ = (id) => document.getElementById(id);

// ----- language picker ---------------------------------------------------------
//
// Flags are drawn as small vector images: Windows shows emoji flags only as letters.

const SVG_NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}

function bands(colors, vertical, weights = colors.map(() => 1)) {
  const total = weights.reduce((a, b) => a + b, 0);
  let pos = 0;
  return colors.map((fill, i) => {
    const size = (vertical ? 20 : 14) * weights[i] / total;
    const rect = vertical
      ? svg("rect", { x: pos, y: 0, width: size + 0.05, height: 14, fill })
      : svg("rect", { x: 0, y: pos, width: 20, height: size + 0.05, fill });
    pos += size;
    return rect;
  });
}

const FLAGS = {
  de: () => bands(["#000000", "#DD0000", "#FFCE00"], false),
  gsw: () => [
    svg("rect", { width: 20, height: 14, fill: "#DA291C" }),
    svg("rect", { x: 8.6, y: 3, width: 2.8, height: 8, fill: "#FFFFFF" }),
    svg("rect", { x: 6, y: 5.6, width: 8, height: 2.8, fill: "#FFFFFF" }),
  ],
  it: () => bands(["#009246", "#FFFFFF", "#CE2B37"], true),
  fr: () => bands(["#0055A4", "#FFFFFF", "#EF4135"], true),
  es: () => bands(["#AA151B", "#F1BF00", "#AA151B"], false, [1, 2, 1]),
  pt: () => [
    ...bands(["#006600", "#FF0000"], true, [2, 3]),
    svg("circle", { cx: 8, cy: 7, r: 3, fill: "#FFE000", stroke: "#1A2550", "stroke-width": 0.4 }),
  ],
  en: () => [
    svg("rect", { width: 20, height: 14, fill: "#012169" }),
    svg("path", { d: "M0 0L20 14M20 0L0 14", stroke: "#FFFFFF", "stroke-width": 3 }),
    svg("path", { d: "M0 0L20 14M20 0L0 14", stroke: "#C8102E", "stroke-width": 1 }),
    svg("path", { d: "M10 0V14M0 7H20", stroke: "#FFFFFF", "stroke-width": 4 }),
    svg("path", { d: "M10 0V14M0 7H20", stroke: "#C8102E", "stroke-width": 2 }),
  ],
  system: () => [
    svg("circle", { cx: 10, cy: 7, r: 6, fill: "none", stroke: "#3B82F6", "stroke-width": 1.4 }),
    svg("ellipse", { cx: 10, cy: 7, rx: 2.6, ry: 6, fill: "none", stroke: "#3B82F6",
      "stroke-width": 1.2 }),
    svg("path", { d: "M4 7H16", stroke: "#3B82F6", "stroke-width": 1.2 }),
  ],
};

function flag(code) {
  const el = svg("svg", { viewBox: "0 0 20 14", width: 24, height: 17, class: "flag",
    "aria-hidden": "true" });
  el.append(...(FLAGS[code] || FLAGS.system)());
  return el;
}

function openLanguages() {
  $("lang-list").replaceChildren(...LANGUAGES.map(([code, name]) => h("button", {
    type: "button", class: code === LANG_CHOICE ? "lang on" : "lang",
    onclick: () => {
      try { localStorage.setItem("airman.lang", code); } catch { /* private mode */ }
      window.location.reload();
    },
  }, flag(code), name)));
  $("lang-sheet").hidden = false;
}

function initLanguageButton() {
  const button = $("lang-toggle");
  if (!button) return;
  button.replaceChildren(flag(LANG_CHOICE));
  button.setAttribute("aria-label", t("language"));
  button.addEventListener("click", openLanguages);
  $("lang-cancel").addEventListener("click", () => { $("lang-sheet").hidden = true; });
  $("lang-sheet").addEventListener("click", (e) => {
    if (e.target === $("lang-sheet")) $("lang-sheet").hidden = true;
  });
}

// ----- day / night ---------------------------------------------------------------

const THEME_COLORS = { day: "#FFC62B", night: "#1A2550" };
const systemNight = window.matchMedia("(prefers-color-scheme: dark)");

function storedTheme() {
  try { return localStorage.getItem("airman.theme"); } catch { return null; }
}

function currentTheme() {
  return storedTheme() || (systemNight.matches ? "night" : "day");
}

// At night the header shows the moon or the laughing note; a tap on it switches,
// and the choice is kept for night mode on this device.
function storedNightMascot() {
  try { return localStorage.getItem("airman.nightMascot"); } catch { return null; }
}

function applyTheme() {
  const theme = currentTheme();
  if (storedTheme()) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
  if (storedTheme()) {
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
      meta.content = THEME_COLORS[theme];
    });
  }
  // Favicon and logos follow the theme. Without a stored choice the favicon
  // links keep their media queries, so the browser follows the device itself.
  for (const name of ["day", "night"]) {
    const link = $(`favicon-${name}`);
    if (link) link.href = `icons/${storedTheme() ? theme : name}/favicon.svg`;
  }
  document.querySelectorAll(".theme-logo").forEach((img) => {
    img.src = `icons/${theme}/airman-icon.svg`;
  });
  // Mascot: by day the sun once chosen, else the note; at night the moon or the
  // note, as last picked with a tap (the moon once night mode was chosen).
  let banner = storedTheme() ? theme : "default";
  if (theme === "night") {
    const mascot = storedNightMascot() || (storedTheme() ? "moon" : "note");
    banner = mascot === "moon" ? "night" : "default";
    document.documentElement.dataset.nightLook = mascot;
  } else {
    delete document.documentElement.dataset.nightLook;
  }
  document.documentElement.dataset.banner = banner;
  const mascotButton = $("mascot");
  if (mascotButton) mascotButton.setAttribute("aria-label", t("switchMascot"));
  const button = $("theme-toggle");
  if (button) {
    // The button shows what a tap switches to.
    button.querySelector(".icon-sun").toggleAttribute("hidden", theme !== "night");
    button.querySelector(".icon-moon").toggleAttribute("hidden", theme === "night");
    button.setAttribute("aria-label", t(theme === "night" ? "toDay" : "toNight"));
  }
}

function toggleNightMascot() {
  if (currentTheme() !== "night") return;
  const next = document.documentElement.dataset.nightLook === "moon" ? "note" : "moon";
  try { localStorage.setItem("airman.nightMascot", next); } catch { /* private mode */ }
  applyTheme();
}

function toggleTheme() {
  const next = currentTheme() === "night" ? "day" : "night";
  try { localStorage.setItem("airman.theme", next); } catch { /* private mode */ }
  applyTheme();
}

applyTheme();
// Safari before iOS 14 only knows the old addListener.
if (systemNight.addEventListener) systemNight.addEventListener("change", applyTheme);
else if (systemNight.addListener) systemNight.addListener(applyTheme);

// ----- API ---------------------------------------------------------------------

class LoginRequired extends Error {}

async function api(path, body) {
  const options = body === undefined
    ? { credentials: "same-origin" }
    : {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      };
  const response = await fetch(path, options);
  if (response.status === 401 && path !== "/api/login") throw new LoginRequired();
  let data = {};
  try { data = await response.json(); } catch { /* empty body */ }
  if (!response.ok) {
    const error = new Error(data.error || response.statusText);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

// ----- state -------------------------------------------------------------------

const ui = {
  state: null,
  source: (() => {
    try { return localStorage.getItem("airman.source") || "youtube"; } catch { return "youtube"; }
  })(),
  results: [],
  resultsAreList: false,
  pending: null,
  cards: new Map(),
  pollTimer: null,
  volumeBusyUntil: new Map(),
};

// Shown when the page can not start (no connection, a script error in an old
// browser): otherwise only the background would be visible.
function showStartError(message) {
  let box = $("start-error");
  if (!box) {
    box = document.createElement("div");
    box.id = "start-error";
    box.className = "start-error";
    box.setAttribute("role", "alert");
    document.body.appendChild(box);
  }
  let text = "AirMan could not start";
  let again = "Reload";
  try {
    text = t("startFailed");
    again = t("reload");
  } catch (e) { /* the texts themselves may be what failed */ }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "primary";
  button.textContent = again;
  button.addEventListener("click", () => location.reload());
  const p = document.createElement("p");
  p.textContent = message ? `${text}: ${message}` : text;
  while (box.firstChild) box.removeChild(box.firstChild);
  box.appendChild(p);
  box.appendChild(button);
}

function hideStartError() {
  const box = $("start-error");
  if (box) box.remove();
}

window.addEventListener("error", (event) => {
  if ($("app").hidden && $("login").hidden) showStartError(event.message);
});

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 3000);
}

function showError(err) {
  if (err instanceof LoginRequired) return showLogin();
  toast(t("error", { e: err.message }));
}

// ----- login -------------------------------------------------------------------

function showLogin() {
  stopPolling();
  $("app").hidden = true;
  $("login").hidden = false;
  document.documentElement.dataset.view = "login";
  $("password").focus();
}

async function onLogin(event) {
  event.preventDefault();
  const errorEl = $("login-error");
  errorEl.textContent = "";
  try {
    await api("/api/login", { password: $("password").value });
    $("password").value = "";
    await start();
  } catch (err) {
    if (err.status === 429) errorEl.textContent = t("locked", { s: err.data.retry_after });
    else errorEl.textContent = t("wrongPassword");
  }
}

async function onLogout() {
  try { await api("/api/logout", {}); } catch { /* ignore */ }
  showLogin();
}

// ----- simple / playlist mode ---------------------------------------------------

function playlistMode() {
  try { return localStorage.getItem("airman.mode") === "playlist"; } catch { return false; }
}

function renderModeToggle() {
  const box = $("mode-toggle");
  if (!box) return;
  const current = playlistMode() ? "playlist" : "simple";
  box.replaceChildren(...[["simple", "modeSimple"], ["playlist", "modePlaylist"]].map(([mode, key]) =>
    h("button", {
      type: "button", "aria-pressed": String(mode === current),
      onclick: () => {
        try { localStorage.setItem("airman.mode", mode); } catch { /* private mode */ }
        renderModeToggle();
        renderSpeakers();
      },
    }, t(key))));
}

// ----- search ------------------------------------------------------------------

function renderTabs() {
  const tabs = $("source-tabs");
  tabs.replaceChildren(...ui.state.sources.map((src) =>
    h("button", {
      type: "button",
      role: "tab",
      "aria-selected": String(src.name === ui.source),
      onclick: () => {
        ui.source = src.name;
        try { localStorage.setItem("airman.source", src.name); } catch { /* private mode */ }
        renderTabs();
        // The files tab lists everything right away; other tabs need a search term.
        if (src.name === "local" || $("query").value.trim()) onSearch();
      },
    }, src.name === "local" ? t("files") : src.label)));
  if (!ui.state.sources.some((s) => s.name === ui.source)) {
    ui.source = (ui.state.sources[0] || {}).name || "youtube";
  }
}

async function onSearch(event) {
  if (event) event.preventDefault();
  const q = $("query").value.trim();
  if (!q && ui.source !== "local") return;
  $("query").blur();
  $("results").hidden = false;
  $("results-info").textContent = t("searching");
  $("results-list").replaceChildren();
  try {
    const data = await api("/api/search", { q, source: ui.source });
    ui.results = data.results;
    // A pasted playlist link becomes a queue; a normal search does not.
    ui.resultsAreList = /^https?:\/\//.test(q) && data.results.length > 1;
    renderResults();
  } catch (err) {
    $("results-info").textContent = "";
    showError(err);
  }
}

function trackLine(track) {
  const offline = track.offline && track.source === "youtube" ? `⬇ ${t("offlineBadge")}` : "";
  const parts = [track.live ? t("live") : "", offline, track.subtitle, formatSize(track.size)]
    .filter(Boolean);
  const sub = [parts.join(" · ")];
  if (track.duration) sub.push(parts.length ? " · " : "", timeNode(track.duration, false));
  const hasSub = parts.length || track.duration;
  return [h("span", { class: "title" }, track.title),
    hasSub ? h("span", { class: "subtitle" }, ...sub) : null];
}

// File size of songs stored on this computer: MB, from 1 GB on in GB.
function formatSize(bytes) {
  if (!bytes) return "";
  const locale = LANG === "gsw" ? "de-CH" : LANG;
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toLocaleString(locale, { maximumFractionDigits: 1 })} GB`;
  const mb = bytes / 1024 ** 2;
  return `${mb.toLocaleString(locale, { maximumFractionDigits: mb < 10 ? 1 : 0 })} MB`;
}

// Small preview: YouTube image through AirMan, otherwise a symbol.
function trackRow(track) {
  const icon = () => h("span", { class: "thumb thumb-icon", "aria-hidden": "true" },
    track.live ? "📻" : "🎵");
  const thumb = track.thumb
    ? h("img", { class: "thumb", src: `thumbs/${encodeURIComponent(track.thumb)}.jpg`,
      alt: "", loading: "lazy", width: "64", height: "36",
      onerror: (e) => e.target.replaceWith(icon()) })
    : icon();
  return [thumb, h("span", { class: "text" }, ...trackLine(track).filter(Boolean))];
}

function renderResults() {
  const files = ui.source === "local";
  $("upload-btn").hidden = !files;
  $("results-info").textContent = ui.results.length
    ? t("results", { n: ui.results.length }) : t(files ? "filesEmpty" : "noResults");
  $("results-list").replaceChildren(...ui.results.map((track, i) => {
    const row = h("li", { class: "result-row" },
      h("button", { class: "result", type: "button", onclick: () => choose(i) }, trackRow(track)));
    if (track.source === "local" && track.ref.startsWith("u:")) {
      row.append(h("button", { type: "button", class: "icon-btn small", "aria-label": t("deleteFile"),
        onclick: () => deleteUpload(track) }, "✕"));
    }
    return row;
  }));
}

// ----- uploads ---------------------------------------------------------------------

async function deleteUpload(track) {
  if (!window.confirm(t("deleteConfirm", { t: track.title }))) return;
  try {
    await api("/api/files/delete", { ref: track.ref });
    onSearch();
  } catch (err) {
    showError(err);
  }
}

// XMLHttpRequest instead of fetch: only it reports upload progress.
function uploadFiles(files) {
  if (!files.length) return;
  const form = new FormData();
  for (const file of files) form.append("file", file, file.name);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.setRequestHeader("X-AirMan-Upload", "1");
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) toast(t("uploading", { p: Math.round((e.loaded / e.total) * 100) }));
  };
  xhr.onload = () => {
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
    if (xhr.status === 401) return showLogin();
    if (xhr.status !== 200) {
      toast(t("uploadFailed", { e: data.error || xhr.statusText }));
    } else {
      toast(t("uploaded", { n: data.saved.length }));
    }
    onSearch();
  };
  xhr.onerror = () => toast(t("uploadFailed", { e: "network" }));
  xhr.send(form);
}

function closeResults() {
  $("results").hidden = true;
  ui.results = [];
}

// ----- choosing a speaker --------------------------------------------------------

function playableSpeakers() {
  const list = ui.state.speakers.filter((s) => s.online && !s.needs_pairing);
  const last = ui.state.last_speaker;
  return list.sort((a, b) => (b.id === last) - (a.id === last));
}

function choose(index) {
  const tracks = ui.resultsAreList ? ui.results : [ui.results[index]];
  const start = ui.resultsAreList ? index : 0;
  ui.pending = { tracks, index: start };
  const speakers = playableSpeakers();
  $("sheet-title").textContent = ui.results[index].title;
  $("sheet-hint").textContent = t(playlistMode() ? "addTo" : "playOn");
  $("sheet-speakers").replaceChildren(...speakers.map((s, i) =>
    h("button", { type: "button", class: i === 0 ? "primary" : "", onclick: () => playOn(s) },
      s.group ? `${s.name} · ${t("groupName", { g: s.group })}` : s.name)));
  $("sheet").hidden = false;
}

function closeSheet() {
  $("sheet").hidden = true;
  ui.pending = null;
}

async function playOn(speaker) {
  const pending = ui.pending;
  closeSheet();
  if (!pending) return;
  if (playlistMode()) {
    await action(speaker.id, "enqueue", { tracks: pending.tracks.slice(pending.index) });
    toast(t("addedTo", { s: speaker.name }));
  } else {
    await action(speaker.id, "play", pending);
    toast(t("started", { s: speaker.name }));
  }
}

// ----- speaker cards ---------------------------------------------------------------

const LIVE_INTERVAL = 150;
const liveSends = new Map();

// While a slider moves, send its value at most every LIVE_INTERVAL ms
// (the last value always goes out), without re-rendering the card.
function sendLive(key, id, name, body) {
  const entry = liveSends.get(key) || { last: 0, timer: null };
  liveSends.set(key, entry);
  clearTimeout(entry.timer);
  const send = () => {
    entry.last = Date.now();
    api(`/api/speakers/${encodeURIComponent(id)}/${name}`, body).catch(showError);
  };
  const wait = LIVE_INTERVAL - (Date.now() - entry.last);
  if (wait <= 0) send();
  else entry.timer = setTimeout(send, wait);
}

function timeNode(seconds, position = true) {
  const text = position ? formatPosition(seconds) : formatDuration(seconds);
  const cut = text.lastIndexOf(":");
  if (cut < 0) return document.createTextNode(text);
  return h("span", { class: "time-value" }, text.slice(0, cut),
    h("span", { class: "sec" }, text.slice(cut)));
}

// A translated text whose {t} is a time with lighter seconds.
function textWithTime(key, seconds) {
  const [before, after] = t(key, { t: "\u0000" }).split("\u0000");
  return [before, timeNode(seconds), after != null ? after : ""];
}

function formatPosition(seconds) {
  return seconds >= 1 ? formatDuration(seconds) : "00:00";
}

async function action(id, name, body = {}) {
  try {
    const data = await api(`/api/speakers/${encodeURIComponent(id)}/${name}`, body);
    if (data.speakers) {
      ui.state.speakers = data.speakers;  // a group changes several speakers at once
    } else {
      const index = ui.state.speakers.findIndex((s) => s.id === id);
      if (index >= 0) ui.state.speakers[index] = data.speaker;
    }
    if (["play", "replay", "continue", "history"].includes(name)) ui.state.last_speaker = id;
    if (name === "pause" || name === "stop") refresh();  // show the saved resume point
    renderSpeakers();
  } catch (err) {
    // An AirMan server older than this page does not know "pause" yet; its "stop"
    // keeps the position too.
    if (name === "pause" && err.status === 404) return action(id, "stop", body);
    showError(err);
  }
}

// Apple TVs with access control are paired once: the TV shows a PIN, typed here.
function buildPairingCard(speaker) {
  const id = speaker.id;
  const els = { pairing: true };
  els.dot = h("span", { class: "dot" });
  els.name = h("h2");
  els.hint = h("p", { class: "pair-hint" }, t("pairHint"));
  els.pin = h("input", { type: "text", inputmode: "numeric", autocomplete: "one-time-code",
    maxlength: "4", pattern: "[0-9]{4}", placeholder: "PIN", class: "pin" });
  els.form = h("form", { class: "pair-form", hidden: "",
    onsubmit: async (event) => {
      event.preventDefault();
      try {
        await api(`/api/speakers/${encodeURIComponent(id)}/pair_finish`,
          { pin: els.pin.value.trim() });
        toast(t("pairDone"));
        await refresh();
      } catch (err) {
        els.pin.value = "";
        showError(err);
      }
    } },
    els.pin,
    h("button", { type: "submit", class: "primary" }, t("pairConfirm")),
    h("button", { type: "button", onclick: () => {
      els.form.hidden = true;
      els.start.hidden = false;
      api(`/api/speakers/${encodeURIComponent(id)}/pair_cancel`, {}).catch(() => {});
    } }, t("cancel")));
  els.start = h("button", { type: "button", class: "primary", onclick: async () => {
    els.start.disabled = true;
    try {
      await api(`/api/speakers/${encodeURIComponent(id)}/pair_start`, {});
      els.start.hidden = true;
      els.form.hidden = false;
      els.pin.focus();
    } catch (err) {
      showError(err);
    } finally {
      els.start.disabled = false;
    }
  } }, t("pair"));
  els.card = h("article", { class: "card" },
    h("div", { class: "card-head" }, els.dot, els.name),
    els.hint, els.start, els.form);
  return els;
}

function updatePairingCard(els, s) {
  els.card.classList.toggle("offline", !s.online);
  els.name.textContent = s.name;
  els.start.disabled = !s.online;
}

function buildCard(speaker) {
  const id = speaker.id;
  const els = {};
  els.dot = h("span", { class: "dot" });
  els.name = h("h2");
  els.now = h("div", { class: "now" });
  // Two lines each: icon (or resume time) and label, so nothing wraps oddly on phones.
  // Play/pause toggle: pauses while playing, continues where it stopped otherwise.
  els.resumeAt = h("small");
  els.continueLabel = h("span");
  els.continue = h("button", { type: "button", class: "primary stacked",
    onclick: () => {
      const s = findSpeaker(id);
      action(id, s.status === "playing" || s.status === "loading" ? "pause" : "continue");
    } }, els.continueLabel, els.resumeAt);
  els.replay = h("button", { type: "button", class: "stacked",
    onclick: () => action(id, "replay") }, h("span", { class: "icon" }, "↻"), t("restart"));
  els.stop = h("button", { type: "button", class: "stacked",
    onclick: () => action(id, "stop") }, h("span", { class: "icon" }, "■"), t("stop"));
  // Multiroom: speakers with the same group number play the same thing in sync.
  els.group = h("button", { type: "button", class: "group-btn", onclick: () => {
    const s = findSpeaker(id);
    const count = ui.state.group_count || 1;
    action(id, "group", { group: (s.group + 1) % (count + 1) });
  } });
  els.repeat = h("button", { type: "button", onclick: () => {
    const s = findSpeaker(id);
    action(id, "repeat", { mode: REPEAT_NEXT[s.repeat] });
  } });
  els.sleep = h("button", { type: "button", onclick: () => {
    const s = findSpeaker(id);
    const current = s.sleep_remaining ? Math.ceil(s.sleep_remaining / 60) : 0;
    const next = SLEEP_STEPS.find((m) => m > current) || 0;
    action(id, "sleep", { minutes: next });
  } });
  els.prev = h("button", { type: "button", onclick: () => action(id, "previous") }, t("previous"));
  els.next = h("button", { type: "button", onclick: () => action(id, "next") }, t("next"));
  els.posTime = h("span", { class: "time" });
  els.durTime = h("span", { class: "time" });
  els.seek = h("input", {
    type: "range", min: "0", max: "1", step: "1", "aria-label": "Position",
    oninput: () => {
      els.seeking = true;
      els.posTime.replaceChildren(timeNode(Number(els.seek.value)));
    },
    onchange: () => {
      els.seeking = false;
      els.posBase = { progress: Number(els.seek.value), at: Date.now() };
      action(id, "seek", { position: Number(els.seek.value) });
    },
  });
  els.progress = h("div", { class: "progress" }, els.posTime, els.seek, els.durTime);
  els.volumeValue = h("span");
  els.mute = h("button", { type: "button", class: "mute-btn", "aria-label": "Mute",
    onclick: () => action(id, "mute", { muted: !findSpeaker(id).muted }) }, "🔈");
  els.volume = h("input", {
    type: "range", min: "0", max: "100", step: "1", "aria-label": "Volume",
    oninput: () => {
      els.volumeValue.textContent = els.volume.value;
      els.mute.textContent = volumeIcon(Number(els.volume.value));
      ui.volumeBusyUntil.set(id, Date.now() + 2500);
      sendLive(`${id}:volume`, id, "volume", { volume: Number(els.volume.value) });
    },
    onchange: () => {
      ui.volumeBusyUntil.set(id, Date.now() + 2500);
      sendLive(`${id}:volume`, id, "volume", { volume: Number(els.volume.value) });
    },
  });
  els.history = h("ul", { class: "history" });
  els.details = h("details", {}, h("summary", {}, t("history")), els.history);
  els.queueTitle = h("summary");
  els.queueList = h("ol", { class: "queue" });
  els.queueClear = h("button", { type: "button", class: "link",
    onclick: () => action(id, "queue_clear") }, t("clearPlaylist"));
  els.playlist = h("details", { class: "playlist", open: true },
    els.queueTitle, els.queueList, els.queueClear);
  els.queueKey = null;
  els.extra = [];
  if (speaker.kind === "pair") {
    els.test = h("button", { type: "button", onclick: () => action(id, "testtone") }, t("testTone"));
    els.leftChoice = h("div", { class: "more-actions" });
    els.balance = h("input", {
      type: "range", min: "-100", max: "100", step: "5", "aria-label": t("balance"),
      oninput: () => {
        // Snap to the centre so it is easy to hit exactly.
        if (Math.abs(Number(els.balance.value)) <= 5) els.balance.value = "0";
        ui.volumeBusyUntil.set(`${id}:balance`, Date.now() + 2500);
        sendLive(`${id}:balance`, id, "balance", { balance: Number(els.balance.value) / 100 });
      },
      onchange: () => {
        ui.volumeBusyUntil.set(`${id}:balance`, Date.now() + 2500);
        sendLive(`${id}:balance`, id, "balance", { balance: Number(els.balance.value) / 100 });
      },
    });
    els.balanceReset = h("button", { type: "button", class: "link", onclick: () => {
      els.balance.value = "0";
      ui.volumeBusyUntil.delete(`${id}:balance`);
      action(id, "balance", { balance: 0 });
    } }, t("resetCentre"));
    els.leftKey = null;
    els.extra.push(h("details", { class: "stereo" },
      h("summary", {}, t("stereo")),
      h("p", { class: "subtitle" }, t("whichLeft")),
      els.leftChoice,
      h("div", { class: "more-actions" }, els.test),
      h("p", { class: "subtitle" }, t("testHint")),
      h("p", { class: "subtitle" }, t("balance")),
      h("div", { class: "volume" }, h("span", {}, "L"), els.balance, h("span", {}, "R")),
      h("div", { class: "balance-row" }, els.balanceReset),
      h("button", { type: "button", class: "link",
        onclick: async () => { await action(id, "split", { split: true }); refresh(); } },
        t("splitPair"))));
  } else if (speaker.pair_of) {
    const pairId = speaker.pair_of;
    els.join = h("button", { type: "button", class: "link",
      onclick: async () => { await action(pairId, "split", { split: false }); refresh(); } });
    els.extra.push(els.join);
  }
  els.card = h("article", { class: "card" },
    h("div", { class: "card-head" }, els.dot, els.name),
    els.now,
    els.progress,
    h("div", { class: "main-actions" }, els.continue, els.replay, els.stop),
    h("div", { class: "more-actions" }, els.repeat, els.sleep, els.group, els.prev, els.next),
    h("div", { class: "volume" }, els.mute, els.volume, els.volumeValue),
    els.playlist,
    els.details,
    ...els.extra);
  els.historyKey = null;
  return els;
}

function volumeIcon(volume) {
  if (volume <= 0) return "🔇";
  if (volume < 34) return "🔈";
  if (volume < 67) return "🔉";
  return "🔊";
}

function findSpeaker(id) {
  return ui.state.speakers.find((s) => s.id === id);
}

function formatMinutes(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const rest = minutes % 60;
  return rest ? `${Math.floor(minutes / 60)} h ${String(rest).padStart(2, "0")}` :
    `${minutes / 60} h`;
}

function updatePair(els, s) {
  const p = s.pair;
  if ((ui.volumeBusyUntil.get(`${s.id}:balance`) || 0) < Date.now()) {
    els.balance.value = String(Math.round((p.balance || 0) * 100));
  }
  const key = `${p.left.id}|${p.members.map((m) => m.name).join("|")}`;
  if (key !== els.leftKey) {
    els.leftKey = key;
    els.leftChoice.replaceChildren(...p.members.map((m) => h("button", {
      type: "button", class: m.id === p.left.id ? "on" : "",
      onclick: () => action(s.id, "left", { member: m.id }),
    }, `⬅ ${m.name}`)));
  }
}

function updateProgress(els, s) {
  const show = s.status === "playing" && s.seekable && s.track && s.track.duration;
  els.progress.hidden = !show;
  if (!show) {
    els.posBase = null;
    return;
  }
  els.seek.max = String(Math.floor(s.track.duration));
  els.durTime.replaceChildren(timeNode(s.track.duration));
  if (!els.seeking) {
    els.posBase = { progress: s.progress || 0, at: Date.now(), duration: s.track.duration };
    tickProgress(els);
  }
}

// Moves the position slider between two status updates.
function tickProgress(els) {
  if (!els.posBase || els.seeking || els.progress.hidden) return;
  const { progress, at, duration } = els.posBase;
  const now = Math.min(duration, progress + (Date.now() - at) / 1000);
  els.seek.value = String(Math.floor(now));
  els.posTime.replaceChildren(timeNode(now));
}

setInterval(() => ui.cards.forEach(tickProgress), 1000);

function updatePlaylist(els, s) {
  const show = playlistMode();
  els.playlist.hidden = !show;
  if (!show) return;
  const busy = s.status === "playing" || s.status === "loading";
  const queue = s.queue || [];
  els.queueTitle.textContent = t("playlist", { n: queue.length });
  els.queueClear.hidden = !queue.length;
  const key = `${busy}|${s.index}|${queue.map((x) => x.source + x.ref).join("|")}`;
  if (key === els.queueKey) return;
  els.queueKey = key;
  if (!queue.length) {
    els.queueList.replaceChildren(h("li", { class: "muted small empty" }, t("emptyPlaylist")));
    return;
  }
  const move = (from, to) => action(s.id, "queue_move", { from, to });
  els.queueList.replaceChildren(...queue.map((track, i) => h("li",
    { class: busy && i === s.index ? "current" : "" },
    h("button", { type: "button", class: "result",
      onclick: () => action(s.id, "queue_play", { index: i }) }, trackRow(track)),
    h("span", { class: "queue-tools" },
      h("button", { type: "button", class: "icon-btn small", "aria-label": t("moveUp"),
        disabled: i === 0, onclick: () => move(i, i - 1) }, "▲"),
      h("button", { type: "button", class: "icon-btn small", "aria-label": t("moveDown"),
        disabled: i === queue.length - 1, onclick: () => move(i, i + 1) }, "▼"),
      h("button", { type: "button", class: "icon-btn small", "aria-label": t("removeSong"),
        onclick: () => action(s.id, "queue_remove", { index: i }) }, "✕")))));
}

function updateCard(els, s) {
  updatePlaylist(els, s);
  els.card.classList.toggle("offline", !s.online);
  els.name.textContent = s.kind === "pair" ? `${s.name} · ${t("stereoPair")}` : s.name;
  if (s.kind === "pair" && s.pair) updatePair(els, s);
  if (els.join) {
    const pair = (ui.state.pair_names || {})[s.pair_of] || "";
    els.join.textContent = t("joinPair", { p: pair });
  }
  els.dot.className = `dot ${s.status}`;

  let line;
  if (s.track && s.status !== "idle") {
    line = trackLine(s.track);
    if (s.status === "loading") {
      const d = s.download;
      const text = d
        ? t("downloading", {
          p: d.fraction != null ? `${Math.round(d.fraction * 100)} %` : "",
          eta: d.eta ? t("timeLeft", { t: formatPosition(d.eta) }) : "",
        })
        : t("loading");
      line[1] = h("span", { class: "subtitle" }, text);
      if (d && d.fraction != null) {
        line.push(h("progress", { class: "download", max: "1", value: String(d.fraction) }));
      }
    }
  } else if (!s.online) {
    line = [h("span", { class: "subtitle" }, t("offline"))];
  } else if (s.error) {
    const msg = s.error === "interrupted" ? t("interrupted") : t("error", { e: s.error });
    line = [h("span", { class: "subtitle" }, msg)];
  } else if (s.history.length) {
    line = [h("span", { class: "title muted" }, t("lastPlayed", { t: s.history[0].title }))];
  } else {
    line = [h("span", { class: "subtitle" }, t("nothingYet"))];
  }
  els.now.replaceChildren(...line.filter(Boolean));

  const busy = s.status === "playing" || s.status === "loading";
  els.replay.disabled = !s.online || (!busy && !s.history.length);
  els.continue.disabled = !s.online || (!busy && !s.resume && !s.history.length);
  els.continueLabel.textContent = busy ? `⏸ ${t("pause")}` : `▶ ${t("continue")}`;
  const resumeAt = s.resume && !s.resume.live && s.resume.position >= 5 ? s.resume.position : 0;
  els.resumeAt.replaceChildren(...(resumeAt && !busy ? textWithTime("resumeAt", resumeAt) : []));
  els.resumeAt.hidden = !resumeAt || busy;
  updateProgress(els, s);
  els.stop.disabled = !busy;
  els.repeat.textContent = t(REPEAT_LABEL[s.repeat]);
  els.group.textContent = `🔗 ${t("groupName", { g: s.group || "–" })}`;
  els.group.classList.toggle("on", s.group > 0);
  els.group.setAttribute("aria-label", s.group ? t("groupOn", { g: s.group }) : t("groupOff"));
  els.group.title = els.group.getAttribute("aria-label");
  // Five colours, then they repeat.
  els.card.dataset.group = s.group ? String(((s.group - 1) % 5) + 1) : "";
  els.repeat.classList.toggle("on", s.repeat !== "off");
  const minutes = s.sleep_remaining ? Math.ceil(s.sleep_remaining / 60) : 0;
  els.sleep.textContent = minutes ? t("sleepOn", { m: formatMinutes(minutes) }) : t("sleepOff");
  els.sleep.classList.toggle("on", minutes > 0);
  const multi = busy && s.queue_length > 1;
  els.prev.hidden = !multi;
  els.next.hidden = !multi;

  els.mute.textContent = volumeIcon(s.muted ? 0 : s.volume);
  els.mute.setAttribute("aria-pressed", String(s.muted));
  els.mute.classList.toggle("on", s.muted);
  els.volume.classList.toggle("muted", s.muted);
  if ((ui.volumeBusyUntil.get(s.id) || 0) < Date.now()) {
    els.volume.value = String(Math.round(s.volume));
    els.volumeValue.textContent = s.muted ? "–" : String(Math.round(s.volume));
  }
  if (s.fading) els.sleep.textContent = `🌙↘ ${els.sleep.textContent.replace("🌙 ", "")}`;

  const historyKey = s.history.map((x) => x.source + x.ref).join("|");
  if (historyKey !== els.historyKey) {
    els.historyKey = historyKey;
    els.history.replaceChildren(...s.history.map((track, i) =>
      h("li", {}, h("button", {
        class: "result", type: "button", onclick: () => action(s.id, "history", { index: i }),
      }, trackRow(track)))));
    els.details.hidden = !s.history.length;
  }
}

function renderDiskWarning() {
  const disk = ui.state.disk;
  const banner = $("disk-warning");
  banner.hidden = !(disk && disk.low);
  if (disk && disk.low) {
    const gb = (disk.free / 1024 ** 3).toLocaleString(LANG === "gsw" ? "de-CH" : LANG,
      { maximumFractionDigits: 1 });
    banner.textContent = t("lowDisk", { g: gb });
  }
}

function renderSpeakers() {
  renderDiskWarning();
  const container = $("speakers");
  const speakers = ui.state.speakers;
  $("no-speakers").hidden = speakers.length > 0;
  const seen = new Set();
  for (const s of speakers) {
    let els = ui.cards.get(s.id);
    if (els && Boolean(els.pairing) !== Boolean(s.needs_pairing)) {
      els.card.remove();  // just paired: becomes a normal speaker card
      els = null;
    }
    if (!els) {
      els = s.needs_pairing ? buildPairingCard(s) : buildCard(s);
      ui.cards.set(s.id, els);
    }
    if (els.pairing) updatePairingCard(els, s);
    else updateCard(els, s);
    seen.add(s.id);
  }
  for (const [id, els] of ui.cards) {
    if (!seen.has(id)) {
      els.card.remove();
      ui.cards.delete(id);
    }
  }
  // Keep DOM order equal to server order without rebuilding cards.
  speakers.forEach((s, i) => {
    const card = ui.cards.get(s.id).card;
    if (container.children[i] !== card) container.insertBefore(card, container.children[i] || null);
  });
}

// ----- polling -------------------------------------------------------------------

async function refresh() {
  try {
    ui.state = await api("/api/state");
    renderSpeakers();
  } catch (err) {
    if (err instanceof LoginRequired) showLogin();
  }
}

function startPolling() {
  stopPolling();
  const tick = async () => {
    await refresh();
    ui.pollTimer = setTimeout(tick, document.hidden ? 15000 : 2000);
  };
  ui.pollTimer = setTimeout(tick, 2000);
}

function stopPolling() {
  clearTimeout(ui.pollTimer);
  ui.pollTimer = null;
}

// ----- logs ------------------------------------------------------------------------

const MAIL_BODY_LIMIT = 12000;
const ISSUE_URL = "https://github.com/pgadient/AirMan/issues/new";

async function fetchLogs() {
  const response = await fetch("/api/logs", { credentials: "same-origin" });
  if (response.status === 401) throw new LoginRequired();
  if (!response.ok) throw new Error(response.statusText);
  return response.text();
}

function issueLink() {
  // Only versions go into the link; the logs are pasted by hand after a look at them.
  const params = new URLSearchParams({
    template: "bug_report.yml",
    version: ui.state.system || `AirMan ${ui.state.version}`,
  });
  return `${ISSUE_URL}?${params}`;
}

async function copyLogs() {
  try {
    await navigator.clipboard.writeText(await fetchLogs());
    toast(t("copied"));
  } catch (err) {
    showError(err);
  }
}

function openLogs() {
  const email = ui.state.support_email;
  const issue = h("a", { class: "button primary", href: issueLink(), target: "_blank",
    rel: "noopener noreferrer" }, t("reportIssue"));
  const copy = h("button", { type: "button", onclick: copyLogs }, t("copyLogs"));
  const mail = h("button", { type: "button", onclick: () => mailLogs(email) },
    email ? t("logsMail", { e: email }) : t("logsMailNoAddress"));
  const share = h("button", { type: "button", onclick: shareLogs }, t("logsShare"));
  $("logs-actions").replaceChildren(issue, copy, mail, share);
  $("logs-sheet").hidden = false;
}

function closeLogs() {
  $("logs-sheet").hidden = true;
}

async function mailLogs(email) {
  try {
    let text = await fetchLogs();
    if (text.length > MAIL_BODY_LIMIT) {
      // Keep the header (versions, speakers) and the most recent lines.
      const head = text.slice(0, text.indexOf("Log:") + 4);
      text = `${head}\n${t("logsTruncated")}\n…${text.slice(-(MAIL_BODY_LIMIT - head.length))}`;
    }
    const subject = `AirMan logs ${new Date().toISOString().slice(0, 16).replace("T", " ")}`;
    const to = email ? encodeURIComponent(email) : "";
    window.location.href =
      `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
    closeLogs();
  } catch (err) {
    showError(err);
  }
}

async function shareLogs() {
  try {
    const text = await fetchLogs();
    const name = `airman-logs-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`;
    const file = new File([text], name, { type: "text/plain" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: "AirMan logs" });
    } else {
      const url = URL.createObjectURL(file);
      const link = h("a", { href: url, download: name });
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
    closeLogs();
  } catch (err) {
    if (!err || err.name !== "AbortError") showError(err);
  }
}

async function onRescan() {
  toast(t("scanning"));
  try {
    ui.state = await api("/api/rescan", {});
    renderSpeakers();
  } catch (err) {
    showError(err);
  }
}

// ----- start -------------------------------------------------------------------------

function formatDuration(seconds) {
  if (!seconds) return "";
  const s = Math.round(seconds);
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  // Always two digits per part (01:50:47, 05:03), so hours stand out from minutes.
  const two = (n) => String(n).padStart(2, "0");
  return hh ? `${two(hh)}:${two(mm)}:${ss}` : `${two(mm)}:${ss}`;
}

function applyTexts() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
}

async function start() {
  try {
    ui.state = await api("/api/state");
  } catch (err) {
    if (err instanceof LoginRequired) return showLogin();
    // Not reachable or an error: say so on the page (not just the sky) and try again.
    showStartError(err.message);
    clearTimeout(start.retry);
    start.retry = setTimeout(start, 5000);
    return;
  }
  clearTimeout(start.retry);
  hideStartError();
  $("login").hidden = true;
  $("app").hidden = false;
  delete document.documentElement.dataset.view;
  $("version").textContent = `AirMan ${ui.state.version}`;
  document.title = `AirMan ${ui.state.version}`;
  renderTabs();
  renderModeToggle();
  renderSpeakers();
  startPolling();
}

document.addEventListener("DOMContentLoaded", () => {
  applyTexts();
  $("login-form").addEventListener("submit", onLogin);
  $("search-form").addEventListener("submit", onSearch);
  $("results-close").addEventListener("click", closeResults);
  $("upload-btn").addEventListener("click", () => $("upload-input").click());
  $("upload-input").addEventListener("change", (e) => {
    uploadFiles([...e.target.files]);
    e.target.value = "";
  });
  $("sheet-cancel").addEventListener("click", closeSheet);
  $("sheet").addEventListener("click", (e) => { if (e.target === $("sheet")) closeSheet(); });
  $("rescan").addEventListener("click", onRescan);
  $("logout").addEventListener("click", onLogout);
  $("report-bug").addEventListener("click", openLogs);
  initLanguageButton();
  $("theme-toggle").addEventListener("click", toggleTheme);
  $("mascot").addEventListener("click", toggleNightMascot);
  applyTheme();
  $("logs-cancel").addEventListener("click", closeLogs);
  $("logs-sheet").addEventListener("click", (e) => { if (e.target === $("logs-sheet")) closeLogs(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  start();
});
