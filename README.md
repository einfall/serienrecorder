SerienRecorder
==============

Der SerienRecorder ist ein Plug-In für auf Enigma2 basierende Linux Set-Top-Boxen.

Das SerienRecorder Plug-In erleichtert das Aufnehmen von Serien, indem für ausgewählte Serien automatisch Timer angelegt werden.
Dabei überwacht das SerienRecorder Plug-In ob eine Folge bereits aufgenommen wurde oder nicht, sodass es zu keinen Mehrfachaufnahmen kommt.

Der Benutzer kann sog. Serien Marker für die Serien anlegen, die vom SerienRecorder überwacht werden sollen. Für jeden Serien Marker kann konfiguriert werden, welche Staffeln in die Überwachung einbezogen werden.
Der SerienRecorder holt seine Informationen aus dem Internet, es werden genaue Folgen-Informationen abgerufen, so können diese in den Timer und damit in die Aufnahmeinformationen aufgenommen werden, also z. B. „S01E10 – Der Baum“

Webinterface
---------------
Ab sofort kann der SerienRecorder optional um ein Webinterface erweitert werden.

Das SerienRecorder Webinterface stellt eine Benutzeroberfläche im Webbrowser zur Verfügung,
mit der man den SerienRecorder von quasi überall bedienen kann.

**DOWNLOAD:**

Die aktuelle Version des SerienRecorder Webinterfaces kann ab sofort immer hier heruntergeladen werden: github.com/einfall/serienrecorder/releases/latest
Am Ende des Changelogs, bei den Assets (muss evtl. aufgeklappt werden) findet man das Paket 'serienrecorder-webinterface_x.x-y.y.y.zip' zum Download.
Dabei bezieht sich die x.x auf die Schnittstellenversion und y.y.y auf die Webinterface Version (siehe auch HINWEISE bzw. UPDATES)

**VORAUSSETZUNGEN:**

Damit man das SerienRecorder Webinterface verwenden kann, muss auf der Box ein allgemeines Webinterface (z.B. OpenWebif) installiert und aktiviert sein.
Auf den Dreamboxen funktioniert es natürlich auch mit dem Dreambox Webinterface.
Der SerienRecorder muss mindestens in der Version 4.2.3 installiert sein.

**INSTALLATION:**
1. Installationspaket auspacken
2. Den Ordner 'web-data' in das SerienRecorder Installationsverzeichnis (/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder) hochladen.
3. Die Einstellungen des SerienRecorders auf der Box öffnen.
4. Im Bereich 'Benutzeroberfläche' ist jetzt die Option 'SerienRecorder Webinterface aktivieren' verfügbar - diese aktivieren.
5. Die Einstellungen speichern und den SerienRecorder verlassen.
6. Die Box neustarten, damit die Schnittstelle initialisiert wird.
7. Im Webbrowser das Webinterface aufrufen 'http://<ip-der-box>/serienrecorderui/' (siehe auch BENUTZUNG)

**BENUTZUNG:**

Wenn das Webinterface der Box (z.B. OpenWebif) aktuell ist, taucht der SerienRecorder unter 'Extras' auf und kann von dort aufgerufen werden.
Alternativ kann es auch direkt über 'http://<ip-der-box>/serienrecorderui/' aufgerufen werden.

**HINWEISE:**

Das SerienRecorder Webinterface befindet sich im Moment noch in der Entwicklung, es sind noch nicht alle Funktionen freigeschaltet, bzw. umgesetzt. Für die Kommunikation mit dem SerienRecorder wird eine sog. API verwendet, die der SerienRecorder bereitstellt.
Diese Schnittstelle muss kompatibel mit der Version des SerienRecorder Webinterfaces sein.
Ist sie das nicht, wird beim Aufrufen des SerienRecorder Webinterfaces eine entsprechende Meldung angezeigt.

**UPDATES:**

Es wird drei verschiedene Arten von Updates für das SerienRecorder Webinterface geben:
1. Nur das SerienRecorder Webinterface wird geändert => es muss nur der 'web-data' Ordner ausgetauscht werden.
2. Schnittstelle (API) wird geändert => es muss eine neue Version des SerienRecorders installiert werden.
3. SerienRecorder Webinterface und Schnittstelle werden geändert => Es muss eine neue SerienRecorder Version installiert und der 'web-data' Ordner ausgetauscht werden.

Im SerienRecorder kann man ablesen welche Schnittstellen Version die aktuelle Installation hat:
1. In den SerienRecorder Einstellungen wird im Beschreibungstext der Option 'SerienRecorder Webinterface aktivieren' die Schnittstellen Version ausgegeben.
2. Nach einem Timer-Suchlauf wird im Log die Schnittstellen Version ausgegeben.
3. Im SerienRecorder Webinterface wird auf der Startseite unter 'Systeminformationen' die API Version ausgegeben: <aktuelle Version> / <benötigte Version>

Der Dateiname des SerienRecorder Webinterface Pakets enthält sowohl die benötigte Schnittstellen Version wie auch die Webinterface Version:
'serienrecorder-webinterface_2.0-0.7.0.zip' - in diesem Fall wird die Schnittstellen Version '2.0' benötigt, die Webinterface Version ist '0.7.0'

Bei einem Update sollte man zunächst den kompletten web-data Ordner im SerienRecorder Ordner auf der Box löschen bevor man das Update kopiert, bei einem Update haben die meisten Dateien neue Namen bekommen und werden beim Kopieren nicht ersetzt.
Da der Browser die Anwendung im Cache behält, nachdem Update ein "harten Reload" des Browsers durchführen "Strg + F5" oder den Cache löschen.

**FEHLER MELDEN:**

Beim SerienRecorder Webinterface handelt es sich um eine sog. responsive Webapp - das bedeutet, dass sich das Aussehen stufenweise an die Bildschirmauflösung anpasst.
Es werden also z.B. auf einem Smartphone Bildschirm weniger und/oder andere Inhalte angezeigt. Oft sind die Inhalte dort anders angeordnet. Deswegen ist es bei der Fehlerbeschreibung wichtig mitzuteilen, mit welcher Bildschirmauflösung der Fehler auftritt.
Da die Anpassungen des Aussehens stufenweise erfolgen, kann es sein, dass nicht immer das optimale Ergebnis auf jedem Bildschirm dargestellt wird.
Beispiel: Smartphone im Hochformat zeigt eine optimale Darstellung, aber im Querformat ist die Darstellung evtl. nicht optimal, weil dort schon auf die nächste Auflösungsstufe gewechselt wurde, die aber nicht optimal für den Smartphone Bildschirm passt.
Damit muss man dann aber erstmal leben.
