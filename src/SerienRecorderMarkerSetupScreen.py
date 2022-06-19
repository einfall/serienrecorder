# coding=utf-8

# This file contains the SerienRecoder Marker Setup Screen
try:
	import simplejson as json
except ImportError:
	import json
import time

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.ConfigList import ConfigListScreen, ConfigList
from Components.config import config, ConfigInteger, getConfigListEntry, ConfigText, ConfigYesNo, ConfigSelection, NoSave, ConfigClock

from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox

from Tools.Directories import fileExists

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

from .SerienRecorderScreenHelpers import serienRecBaseScreen, InitSkin, setMenuTexts, buttonText_na
from .SerienRecorder import serienRecDataBaseFilePath

from .SerienRecorderHelpers import hasAutoAdjust, PY2
from .SerienRecorderDatabase import SRDatabase

# Tageditor
from Screens.MovieSelection import getPreferredTagEditor

class serienRecMarkerSetup(serienRecBaseScreen, Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, serien_name, serien_wlid, serien_id, serien_fsid):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.list = []
		self.session = session
		self.serien_name = serien_name
		self.serien_id = serien_id
		self.serien_wlid = serien_wlid
		self.serien_fsid = serien_fsid
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.HilfeTexte = {}
		self.fromTime_index = 1
		self.toTime_index = 1
		self.margin_before_index = 1
		self.margin_after_index = 1
		self.NoOfRecords_index = 1

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red": (self.cancel, "Änderungen verwerfen und zurück zur Serien-Marker-Ansicht"),
			"green": (self.save, "Einstellungen speichern und zurück zur Serien-Marker-Ansicht"),
			"blue": (self.resetCover, "Cover zurücksetzen"),
			"cancel": (self.cancel, "Änderungen verwerfen und zurück zur Serien-Marker-Ansicht"),
			"ok": (self.ok, "Fenster für Verzeichnisauswahl öffnen"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"startTeletext": (self.showAbout, "Über dieses Plugin"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions", ], {
			"displayHelp": self.showHelp,
			"displayHelp_long": self.showManual,
		}, 0)

		self.setupSkin()
		if config.plugins.serienRec.showAllButtons.value:
			setMenuTexts(self)

		(AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon,
		 AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags, addToDatabase, updateFromEPG, skipSeriesServer, autoAdjust, epgSeriesName, kindOfTimer, forceRecording) = self.database.getMarkerSettings(self.serien_id)

		if not AufnahmeVerzeichnis:
			AufnahmeVerzeichnis = ""
		self.savetopath = ConfigText(default=AufnahmeVerzeichnis, fixed_size=False, visible_width=50)
		self.seasonsubdir = ConfigSelection(choices=[("-1", "Gemäß Setup (dzt. %s)" % str(
			config.plugins.serienRec.seasonsubdir.value).replace("True", "Ja").replace("False", "Nein")), ("0", "Nein"),
													 ("1", "Ja")], default=str(Staffelverzeichnis))

		if str(Vorlaufzeit).isdigit():
			self.margin_before = ConfigInteger(Vorlaufzeit, (0, 999))
			self.enable_margin_before = ConfigYesNo(default=True)
		else:
			self.margin_before = ConfigInteger(config.plugins.serienRec.margin_before.value, (0, 999))
			self.enable_margin_before = ConfigYesNo(default=False)

		if str(Nachlaufzeit).isdigit():
			self.margin_after = ConfigInteger(Nachlaufzeit, (0, 999))
			self.enable_margin_after = ConfigYesNo(default=True)
		else:
			self.margin_after = ConfigInteger(config.plugins.serienRec.margin_after.value, (0, 999))
			self.enable_margin_after = ConfigYesNo(default=False)

		if str(AnzahlWiederholungen).isdigit():
			self.NoOfRecords = ConfigInteger(AnzahlWiederholungen, (1, 9))
			self.enable_NoOfRecords = ConfigYesNo(default=True)
		else:
			self.NoOfRecords = ConfigInteger(config.plugins.serienRec.NoOfRecords.value, (1, 9))
			self.enable_NoOfRecords = ConfigYesNo(default=False)

		if str(AufnahmezeitVon).isdigit():
			self.fromTime = ConfigClock(default=int(AufnahmezeitVon) * 60 + time.timezone)
			self.enable_fromTime = ConfigYesNo(default=True)
		else:
			self.fromTime = ConfigClock(default=((config.plugins.serienRec.globalFromTime.value[0] * 60) +
												 config.plugins.serienRec.globalFromTime.value[1]) * 60 + time.timezone)
			self.enable_fromTime = ConfigYesNo(default=False)

		if str(AufnahmezeitBis).isdigit():
			self.toTime = ConfigClock(default=int(AufnahmezeitBis) * 60 + time.timezone)
			self.enable_toTime = ConfigYesNo(default=True)
		else:
			self.toTime = ConfigClock(default=((config.plugins.serienRec.globalToTime.value[0] * 60) +
											   config.plugins.serienRec.globalToTime.value[1]) * 60 + time.timezone)
			self.enable_toTime = ConfigYesNo(default=False)

		if str(forceRecording).isdigit():
			self.forceRecording = ConfigYesNo(default=bool(forceRecording))
			self.enable_forceRecording = ConfigYesNo(default=True)
		else:
			self.forceRecording = ConfigYesNo(default=config.plugins.serienRec.forceRecording.value)
			self.enable_forceRecording = ConfigYesNo(default=False)

		if str(vps).isdigit():
			self.override_vps = ConfigYesNo(default=True)
			self.enable_vps = ConfigYesNo(default=bool(vps & 0x1))
			self.enable_vps_savemode = ConfigYesNo(default=bool(vps & 0x2))
		else:
			self.override_vps = ConfigYesNo(default=False)
			self.enable_vps = ConfigYesNo(default=False)
			self.enable_vps_savemode = ConfigYesNo(default=False)

		if str(addToDatabase).isdigit():
			self.addToDatabase = ConfigYesNo(default=bool(addToDatabase))
		else:
			self.addToDatabase = ConfigYesNo(default=True)

		if str(updateFromEPG).isdigit():
			self.updateFromEPG = ConfigYesNo(default=bool(updateFromEPG))
			self.enable_updateFromEPG = ConfigYesNo(default=True)
		else:
			self.updateFromEPG = ConfigYesNo(default=config.plugins.serienRec.eventid.value)
			self.enable_updateFromEPG = ConfigYesNo(default=False)

		if str(kindOfTimer).isdigit():
			self.kindOfTimer = ConfigSelection(choices=[("1", "umschalten"), ("0", "aufnehmen"), ("2", "umschalten und aufnehmen"), ("4", "Erinnerung")], default=str(kindOfTimer))
			self.enable_kindOfTimer = ConfigYesNo(default=True)
		else:
			self.kindOfTimer = ConfigSelection(choices=[("1", "umschalten"), ("0", "aufnehmen"), ("2", "umschalten und aufnehmen"), ("4", "Erinnerung")], default=str(config.plugins.serienRec.kindOfTimer.value))
			self.enable_kindOfTimer = ConfigYesNo(default=False)

		if str(skipSeriesServer).isdigit():
			self.skipSeriesServer = ConfigYesNo(default=bool(skipSeriesServer))
			self.enable_skipSeriesServer = ConfigYesNo(default=True)
		else:
			self.skipSeriesServer = ConfigYesNo(default=config.plugins.serienRec.tvplaner_skipSerienServer.value)
			self.enable_skipSeriesServer = ConfigYesNo(default=False)

		if str(autoAdjust).isdigit():
			self.autoAdjust = ConfigYesNo(default=bool(autoAdjust))
			self.enable_autoAdjust = ConfigYesNo(default=True)
		else:
			self.autoAdjust = ConfigYesNo(default=False)
			self.enable_autoAdjust = ConfigYesNo(default=False)

		self.preferredChannel = ConfigSelection(choices=[("1", "Standard"), ("0", "Alternativ")], default=str(preferredChannel))
		self.useAlternativeChannel = ConfigSelection(choices=[("-1", "Gemäß Setup (dzt. %s)" % str(
			config.plugins.serienRec.useAlternativeChannel.value).replace("True", "Ja").replace("False", "Nein")),
															  ("0", "Nein"), ("1", "Ja")],
													 default=str(useAlternativeChannel))

		# excluded weekdays
		# each weekday is represented by a bit in the database field
		# 0 = Monday to 6 = Sunday, so if all weekdays are excluded we got 1111111 = 127
		if str(excludedWeekdays).isdigit():
			self.enable_excludedWeekdays = ConfigYesNo(default=True)
			self.excludeMonday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 0)))
			self.excludeTuesday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 1)))
			self.excludeWednesday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 2)))
			self.excludeThursday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 3)))
			self.excludeFriday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 4)))
			self.excludeSaturday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 5)))
			self.excludeSunday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 6)))
		else:
			self.enable_excludedWeekdays = ConfigYesNo(default=False)
			self.excludeMonday = ConfigYesNo(default=False)
			self.excludeTuesday = ConfigYesNo(default=False)
			self.excludeWednesday = ConfigYesNo(default=False)
			self.excludeThursday = ConfigYesNo(default=False)
			self.excludeFriday = ConfigYesNo(default=False)
			self.excludeSaturday = ConfigYesNo(default=False)
			self.excludeSunday = ConfigYesNo(default=False)

		# tags
		if tags is None or len(tags) == 0:
			self.serienmarker_tags = []
		else:
			if tags.startswith("(lp1"):
				# tags are pickled
				if PY2:
					import cPickle as pickle
					self.serienmarker_tags = pickle.loads(tags)
				else:
					import pickle
					from .SerienRecorderHelpers import toBinary
					self.serienmarker_tags = pickle.loads(toBinary(tags), encoding="utf-8")
			else:
				import json
				self.serienmarker_tags = json.loads(tags)

		self.tags = NoSave(
			ConfigSelection(choices=[len(self.serienmarker_tags) == 0 and "Keine" or ' '.join(self.serienmarker_tags)]))

		# EPG series name
		if epgSeriesName is None:
			epgSeriesName = ""
		self.epgSeriesName = ConfigText(default=epgSeriesName, fixed_size=False, visible_width=50)

		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self.setInfoText()
		self['config_information_text'].setText(self.HilfeTexte[self.savetopath])
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
		                    [buttonText_na, buttonText_na, buttonText_na],
		                    [buttonText_na, buttonText_na, buttonText_na],
		                    [buttonText_na, buttonText_na, "Hilfe"],
		                    [buttonText_na, buttonText_na, buttonText_na])

		self['text_red'].setText("Abbrechen")
		self['text_green'].setText("Speichern")
		if config.plugins.serienRec.downloadCover.value:
			self['text_blue'].setText("Cover auswählen")
		self['text_ok'].setText("Ordner auswählen")

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self['config'] = ConfigList([])
		self['config'].show()

		self['config_information'].show()
		self['config_information_text'].show()

		self['title'].setText("Serien-Marker - Einstellungen für '%s':" % self.serien_name)
		if not config.plugins.serienRec.showAllButtons.value:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			if config.plugins.serienRec.downloadCover.value:
				self['bt_blue'].show()
			self['bt_ok'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			if config.plugins.serienRec.downloadCover.value:
				self['text_blue'].show()
			self['text_ok'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()
		else:
			self['text_0'].hide()
			self['text_1'].hide()
			self['text_2'].hide()
			self['text_3'].hide()
			self['text_4'].hide()
			self['text_5'].hide()
			self['text_6'].hide()
			self['text_7'].hide()
			self['text_8'].hide()
			self['text_9'].hide()

			self['bt_0'].hide()
			self['bt_1'].hide()
			self['bt_2'].hide()
			self['bt_3'].hide()
			self['bt_4'].hide()
			self['bt_5'].hide()
			self['bt_6'].hide()
			self['bt_7'].hide()
			self['bt_8'].hide()
			self['bt_9'].hide()

	def createConfigList(self):
		self.list = []
		self.list.append(getConfigListEntry("Abweichender Speicherort der Aufnahmen:", self.savetopath))
		if self.savetopath.value:
			self.list.append(getConfigListEntry("Staffel-Verzeichnis anlegen:", self.seasonsubdir))
			self.margin_before_index += 1

		self.list.append(getConfigListEntry("Alternativer Serienname im EPG:", self.epgSeriesName))
		self.margin_after_index = self.margin_before_index + 1

		self.list.append(getConfigListEntry("Aktiviere abweichenden Timervorlauf:", self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry("      Timervorlauf (in Min.):", self.margin_before))
			self.margin_after_index += 1

		self.NoOfRecords_index = self.margin_after_index + 1

		self.list.append(getConfigListEntry("Aktiviere abweichenden Timernachlauf:", self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry("      Timernachlauf (in Min.):", self.margin_after))
			self.NoOfRecords_index += 1

		self.fromTime_index = self.NoOfRecords_index + 1

		self.list.append(getConfigListEntry("Aktiviere abweichende Anzahl der Aufnahmen:", self.enable_NoOfRecords))
		if self.enable_NoOfRecords.value:
			self.list.append(getConfigListEntry("      Anzahl der Aufnahmen:", self.NoOfRecords))
			self.fromTime_index += 1

		self.toTime_index = self.fromTime_index + 1

		self.list.append(getConfigListEntry("Aktiviere abweichende Früheste Zeit für Timer:", self.enable_fromTime))
		if self.enable_fromTime.value:
			self.list.append(getConfigListEntry("      Früheste Zeit für Timer:", self.fromTime))
			self.toTime_index += 1

		self.list.append(getConfigListEntry("Aktiviere abweichende Späteste Zeit für Timer:", self.enable_toTime))
		if self.enable_toTime.value:
			self.list.append(getConfigListEntry("      Späteste Zeit für Timer:", self.toTime))

		self.list.append(getConfigListEntry("Aktiviere abweichende Timererstellung ohne Wiederholung:", self.enable_forceRecording))
		if self.enable_forceRecording.value:
			self.list.append(getConfigListEntry("      Immer Timer anlegen, wenn keine Wiederholung gefunden wird:", self.forceRecording))

		self.list.append(getConfigListEntry("Aktiviere abweichende Timeraktualisierung aus dem EPG:", self.enable_updateFromEPG))
		if self.enable_updateFromEPG.value:
			self.list.append(getConfigListEntry("      Versuche Timer aus dem EPG zu aktualisieren:", self.updateFromEPG))

		self.list.append(getConfigListEntry("Aktiviere abweichende Timer-Art:", self.enable_kindOfTimer))
		if self.enable_kindOfTimer.value:
			self.list.append(getConfigListEntry("      Timer-Art:", self.kindOfTimer))

		if config.plugins.serienRec.tvplaner.value:
			self.list.append(getConfigListEntry("Aktiviere abweichende Timererstellung nur aus der TV-Planer E-Mail:", self.enable_skipSeriesServer))
			if self.enable_skipSeriesServer.value:
				self.list.append(getConfigListEntry("      Timer nur aus der TV-Planer E-Mail anlegen:", self.skipSeriesServer))

		from .SerienRecorder import VPSPluginAvailable
		if VPSPluginAvailable:
			self.list.append(getConfigListEntry("Aktiviere abweichende VPS Einstellungen:", self.override_vps))
			if self.override_vps.value:
				self.list.append(getConfigListEntry("      VPS für diesen Serien-Marker aktivieren:", self.enable_vps))
				if self.enable_vps.value:
					self.list.append(
						getConfigListEntry("            Sicherheitsmodus aktivieren:", self.enable_vps_savemode))

		if hasAutoAdjust():
			self.list.append(getConfigListEntry("Aktiviere abweichende Aufnahmezeitenanpassung aus den EPG Daten:", self.enable_autoAdjust))
			if self.enable_autoAdjust.value:
				self.list.append(getConfigListEntry("      Aufnahmezeiten automatisch an EPG Daten anpassen:", self.autoAdjust))

		self.list.append(getConfigListEntry("Timer in Timer-Liste speichern:", self.addToDatabase))
		self.list.append(getConfigListEntry("Bevorzugte Sender-Liste:", self.preferredChannel))
		self.list.append(getConfigListEntry("Verwende alternative Sender bei Konflikten:", self.useAlternativeChannel))

		self.list.append(getConfigListEntry("Wochentage von der Timererstellung ausschließen:", self.enable_excludedWeekdays))
		if self.enable_excludedWeekdays.value:
			self.list.append(getConfigListEntry("      Montag:", self.excludeMonday))
			self.list.append(getConfigListEntry("      Dienstag:", self.excludeTuesday))
			self.list.append(getConfigListEntry("      Mittwoch:", self.excludeWednesday))
			self.list.append(getConfigListEntry("      Donnerstag:", self.excludeThursday))
			self.list.append(getConfigListEntry("      Freitag:", self.excludeFriday))
			self.list.append(getConfigListEntry("      Samstag:", self.excludeSaturday))
			self.list.append(getConfigListEntry("      Sonntag:", self.excludeSunday))

		self.list.append(getConfigListEntry("Tags:", self.tags))

	def updateMenuValues(self):
		if self['config'].instance.getCurrentIndex() == self.margin_before_index:
			if self.enable_margin_before.value and not self.margin_before.value:
				self.margin_before.value = config.plugins.serienRec.margin_before.value
		elif self['config'].instance.getCurrentIndex() == self.margin_after_index:
			if self.enable_margin_after.value and not self.margin_after.value:
				self.margin_after.value = config.plugins.serienRec.margin_after.value
		elif self['config'].instance.getCurrentIndex() == self.NoOfRecords_index:
			if self.enable_NoOfRecords.value and not self.NoOfRecords.value:
				self.NoOfRecords.value = config.plugins.serienRec.NoOfRecords.value
		elif self['config'].instance.getCurrentIndex() == self.fromTime_index:
			if self.enable_fromTime.value and not self.fromTime.value:
				self.fromTime.value = config.plugins.serienRec.globalFromTime.value
		elif self['config'].instance.getCurrentIndex() == self.toTime_index:
			if self.enable_toTime.value and not self.toTime.value:
				self.toTime.value = config.plugins.serienRec.globalToTime.value
		self.changedEntry()

	def changedEntry(self):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyLeft(self):
		if self['config'].getCurrent()[1] == self.tags:
			self.chooseTags()
		else:
			ConfigListScreen.keyLeft(self)
			self.updateMenuValues()

	def keyRight(self):
		if self['config'].getCurrent()[1] == self.tags:
			self.chooseTags()
		else:
			ConfigListScreen.keyRight(self)
			self.updateMenuValues()

	def keyDown(self):
		# self.changedEntry()
		if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
			self['config'].instance.moveSelectionTo(0)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveDown)

		# self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyUp(self):
		# self.changedEntry()
		if self['config'].instance.getCurrentIndex() < 1:
			self['config'].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveUp)

		# self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def ok(self):
		if self['config'].getCurrent()[1] == self.tags:
			self.chooseTags()
		elif self['config'].getCurrent()[1] == self.epgSeriesName:
			value = self.serien_name if len(self.epgSeriesName.value) == 0 else self.epgSeriesName.value
			self.session.openWithCallback(self.epgSeriesNameEditFinished, NTIVirtualKeyBoard, title="Serien Titel eingeben:", text=value)
		else:
			if self['config'].getCurrent()[1] == self.savetopath:
				if config.plugins.serienRec.seriensubdir.value:
					self.session.openWithCallback(self.openFileSelector, MessageBox,
												  "Hier wird das direkte Aufnahme-Verzeichnis für die Serie ausgewählt, es wird nicht automatisch ein Serien-Ordner angelegt.\n\nMit der blauen Taste kann ein Serien-Ordner manuell angelegt werden.",
												  MessageBox.TYPE_INFO, timeout=15)
				else:
					self.openFileSelector(True)

	def openFileSelector(self, answer):
		if not self.savetopath.value:
			start_dir = config.plugins.serienRec.savetopath.value
		else:
			start_dir = self.savetopath.value

		from .SerienRecorderFileListScreen import serienRecFileListScreen
		self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir, "Aufnahme-Verzeichnis auswählen", self.serien_name)

	def selectedMediaFile(self, res):
		if res is not None:
			if self['config'].instance.getCurrentIndex() == 0:
				#print(res)
				self.savetopath.value = res
				self.changedEntry()

	def epgSeriesNameEditFinished(self, res):
		if res is not None:
			self.epgSeriesName.value = res
			self.changedEntry()

	def tagEditFinished(self, res):
		if res is not None:
			self.serienmarker_tags = res
			self.tags.setChoices([len(res) == 0 and "Keine" or ' '.join(res)])

	def chooseTags(self):
		preferredTagEditor = getPreferredTagEditor()
		if preferredTagEditor:
			self.session.openWithCallback(
				self.tagEditFinished,
				preferredTagEditor,
				self.serienmarker_tags
			)

	def resetCover(self):
		if not config.plugins.serienRec.downloadCover.value:
			return

		from .SerienRecorderCoverSelectorScreen import CoverSelectorScreen
		self.session.open(CoverSelectorScreen, self.serien_wlid, self.serien_name, self.serien_fsid)

	def setInfoText(self):
		self.HilfeTexte = {
			self.savetopath: "Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von '%s' gespeichert werden." % self.serien_name,
			self.seasonsubdir: "Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis für '%s' (z.B.\n'%sSeason 001') erstellt." % (
				self.serien_name, self.savetopath.value),
			self.epgSeriesName: ("Eingabe des Seriennamens wie er im EPG erscheint.\n\n"
			                     "Manchmal kommt es vor, dass eine Serie bei Wunschliste anders heißt als im EPG (z.B. 'Die 2' vs. 'Die Zwei') das führt dazu, dass der SerienRecorder die Sendung nicht im EPG finden und aktualisieren kann.\n"
			                     "Wenn sich der Serienname unterscheidet, kann der Name hier eingegeben werden, um darüber die Sendung im EPG zu finden."),
			self.enable_margin_before: ("Bei 'ja' kann die Vorlaufzeit für Timer von '%s' eingestellt werden.\n"
										"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
										"Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
										"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.margin_before: ("Die Vorlaufzeit für Timer von '%s' in Minuten.\n"
								 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
								 "Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.serien_name,
			self.enable_margin_after: ("Bei 'ja' kann die Nachlaufzeit für Timer von '%s' eingestellt werden.\n"
									   "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
									   "Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
									   "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.margin_after: ("Die Nachlaufzeit für Timer von '%s' in Minuten.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
								"Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.serien_name,
			self.enable_NoOfRecords: (
									 "Bei 'ja' kann die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen, eingestellt werden.\n"
									 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.\n"
									 "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.NoOfRecords: ("Die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen.\n"
							   "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.") % self.serien_name,
			self.enable_fromTime: (
								  "Bei 'ja' kann die erlaubte Zeitspanne (ab Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.\n"
								  "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.fromTime: ("Die Uhrzeit, ab wann Aufnahmen von '%s' erlaubt sind.\n"
							"Die erlaubte Zeitspanne beginnt um %s:%s Uhr.\n"
							"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.") % (
				               self.serien_name, str(self.fromTime.value[0]).zfill(2), str(self.fromTime.value[1]).zfill(2)),
			self.enable_toTime: (
								"Bei 'ja' kann die erlaubte Zeitspanne (bis Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.\n"
								"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.toTime: ("Die Uhrzeit, bis wann Aufnahmen von '%s' erlaubt sind.\n"
						  "Die erlaubte Zeitspanne endet um %s:%s Uhr.\n"
						  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.") % (
				             self.serien_name, str(self.toTime.value[0]).zfill(2), str(self.toTime.value[1]).zfill(2)),
			self.enable_forceRecording: (
				                           "Bei 'ja' kann für Timer von '%s' eingestellt werden, ob immer ein Timer angelegt werden soll, wenn keine Wiederholung gefunden wurde.\n"
				                           "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung 'Immer Timer anlegen, wenn keine Wiederholung gefunden wird'.\n"
				                           "Bei 'nein' gilt die Einstellung vom globalen Setup.\n\n"
			                               "Wurde eine abweichende Zeitspanne für diese Serie eingestellt, macht es oft Sinn die Option 'Immer Timer anlegen, wenn keine Wiederholung gefunden wird' zu deaktivieren.") % self.serien_name,
			self.forceRecording: ("Bei 'ja' wird für '%s' auch dann ein Timer erstellt, wenn die Episode außerhalb der eingestellten Zeitspanne liegt und keine Wiederholung gefunden wurde.\n"
			                     "Bei 'nein' werden die Timer dieser Serie nur dann erstellt, wenn die Episoden innerhalb der eingestellten Zeitspanne ausgestrahlt wird.\n"
			                     "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für 'Immer Timer anlegen, wenn keine Wiederholung gefunden wird'.") % self.serien_name,
			self.enable_updateFromEPG: (
								"Bei 'ja' kann für Timer von '%s' eingestellt werden, ob versucht werden soll diesen aus dem EPG zu aktualisieren.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Timeraktualisierung aus dem EPG.\n"
								"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.updateFromEPG: ("Bei 'ja' wird für Timer von '%s' versucht diese aus dem EPG zu aktualisieren.\n"
						  "Bei 'nein' werden die Timer dieser Serie nicht aus dem EPG aktualisiert.\n"
						  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Timeraktualisierung aus dem EPG.") % self.serien_name,
			self.enable_kindOfTimer: (
								"Bei 'ja' kann für Timer von '%s' eingestellt werden, welche Art von Timer angelegt werden soll.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Timer-Art.\n"
								"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.kindOfTimer: ("Es kann ausgewählt werden, wie Timer für '%s' angelegt werden. Die Auswahlmöglichkeiten sind:\n"
			                   "  - 'aufnehmen': Ein 'normaler' Timer wird erstellt\n"
			                   "  - 'umschalten': Es wird ein Timer erstellt, bei dem nur auf den aufzunehmenden Sender umgeschaltet wird. Es erfolgt KEINE Aufnahme\n"
			                   "  - 'umschalten und aufnehmen': Es wird ein Timer erstellt, bei dem vor der Aufnahme auf den aufzunehmenden Sender umgeschaltet wird\n"
			                   "  - 'Erinnerung': Es wird ein Timer erstellt, bei dem lediglich eine Erinnerungs-Nachricht auf dem Bildschirm eingeblendet wird. Es wird weder umgeschaltet, noch erfolgt eine Aufnahme\n"
							   "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Timer-Art.") % self.serien_name,
			self.enable_skipSeriesServer: (
								"Bei 'ja' kann für Timer von '%s' eingestellt werden, ob Timer nur aus der TV-Planer E-Mail angelegt werden sollen.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Timererstellung nur aus der TV-Planer E-Mail.\n"
								"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.skipSeriesServer: ("Bei 'ja' werden Timer von '%s' nur aus der TV-Planer E-Mail erstellt.\n"
						  "Bei 'nein' werden die Timer aus den Daten des SerienServer angelegt.\n"
						  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Timererstellung nur aus der TV-Planer E-Mail.") % self.serien_name,
			self.override_vps: ("Bei 'ja' kann VPS für Timer von '%s' eingestellt werden.\n"
								"Diese Einstellung hat Vorrang gegenüber der Einstellung des Senders für VPS.\n"
								"Bei 'nein' gilt die Einstellung vom Sender.") % self.serien_name,
			self.enable_vps: (
							 "Bei 'ja' wird VPS für '%s' aktiviert. Die Aufnahme startet erst, wenn der Sender den Beginn der Ausstrahlung angibt, "
							 "und endet, wenn der Sender das Ende der Ausstrahlung angibt.\n"
							 "Diese Einstellung hat Vorrang gegenüber der Sender Einstellung für VPS.") % self.serien_name,
			self.enable_vps_savemode: (
									  "Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet. Die programmierten Start- und Endzeiten werden eingehalten.\n"
									  "Die Aufnahme wird nur ggf. früher starten bzw. länger dauern, aber niemals kürzer.\n"
									  "Diese Einstellung hat Vorrang gegenüber der Sender Einstellung für VPS.") % self.serien_name,
			self.enable_autoAdjust: ("Bei 'ja' kann für Timer von '%s' eingestellt werden, ob die Aufnahmezeit automatisch an die EPG Daten angepasst werden soll.\n"
			                        "Diese Einstellung hat Vorrang gegenüber der Einstellung für die automatische Anpassung der Aufnahmezeit an EPG Daten am Sender.\n"
			                         "Bei 'nein' gilt die Einstellung am Sender.") % self.serien_name,
			self.autoAdjust: ("Bei 'ja' wird 'Aufnahmezeit automatisch an EPG Daten anpassen' für Timer von '%s' aktiviert.\n"
			                        "Diese Einstellung hat Vorrang gegenüber der Einstellung für die automatische Anpassung der Aufnahmezeit an EPG Daten am Sender.") % self.serien_name,
			self.addToDatabase: "Bei 'nein' werden für die Timer von '%s' keine Einträge in die Timer-Liste gemacht, sodass die Episoden beliebig oft getimert werden können." % self.serien_name,
			self.preferredChannel: "Auswahl, ob die Standard-Sender oder die alternativen Sender für die Timer von '%s' verwendet werden sollen." % self.serien_name,
			self.useAlternativeChannel: (
										"Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Sender (Standard oder alternativ) zu erstellen, "
										"falls der Timer für '%s' auf dem bevorzugten Sender nicht angelegt werden kann.\n"
										"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Verwendung von alternativen Sendern.\n"
										"Bei 'gemäß Setup' gilt die Einstellung vom globalen Setup.") % self.serien_name,
			self.enable_excludedWeekdays: (
										  "Bei 'ja' können bestimmte Wochentage für die Erstellung von Timern für '%s' ausgenommen werden.\n"
										  "Es werden also an diesen Wochentage für diese Serie keine Timer erstellt.\n"
										  "Bei 'nein' werden alle Wochentage berücksichtigt.") % self.serien_name,
			self.tags: ("Verwaltet die Tags für die Timer, die für %s angelegt werden.\n\n"
						"Um diese Option nutzen zu können, muss das Tageditor Plugin installiert sein.") % self.serien_name

		}

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."

		self["config_information_text"].setText(text)

	def save(self):
		if not self.enable_margin_before.value:
			Vorlaufzeit = None
		else:
			Vorlaufzeit = self.margin_before.value

		if not self.enable_margin_after.value:
			Nachlaufzeit = None
		else:
			Nachlaufzeit = self.margin_after.value

		if not self.enable_NoOfRecords.value:
			AnzahlWiederholungen = None
		else:
			AnzahlWiederholungen = self.NoOfRecords.value

		if not self.enable_fromTime.value:
			AufnahmezeitVon = None
		else:
			AufnahmezeitVon = (self.fromTime.value[0] * 60) + self.fromTime.value[1]

		if not self.enable_toTime.value:
			AufnahmezeitBis = None
		else:
			AufnahmezeitBis = (self.toTime.value[0] * 60) + self.toTime.value[1]

		if not self.enable_forceRecording.value:
			forceRecording = None
		else:
			forceRecording = self.forceRecording.value

		if not self.enable_updateFromEPG.value:
			updateFromEPG = None
		else:
			updateFromEPG = self.updateFromEPG.value

		if not self.enable_kindOfTimer.value:
			kindOfTimer = None
		else:
			kindOfTimer = self.kindOfTimer.value

		if not self.enable_skipSeriesServer.value:
			skipSeriesServer = None
		else:
			skipSeriesServer = self.skipSeriesServer.value

		if not self.override_vps.value:
			vpsSettings = None
		else:
			vpsSettings = (int(self.enable_vps_savemode.value) << 1) + int(self.enable_vps.value)

		if not self.enable_autoAdjust.value:
			autoAdjust = None
		else:
			autoAdjust = self.autoAdjust.value

		if (not self.savetopath.value) or (self.savetopath.value == ""):
			Staffelverzeichnis = -1
		else:
			Staffelverzeichnis = self.seasonsubdir.value

		if not self.enable_excludedWeekdays.value:
			excludedWeekdays = None
		else:
			excludedWeekdays = 0
			excludedWeekdays |= (self.excludeMonday.value << 0)
			excludedWeekdays |= (self.excludeTuesday.value << 1)
			excludedWeekdays |= (self.excludeWednesday.value << 2)
			excludedWeekdays |= (self.excludeThursday.value << 3)
			excludedWeekdays |= (self.excludeFriday.value << 4)
			excludedWeekdays |= (self.excludeSaturday.value << 5)
			excludedWeekdays |= (self.excludeSunday.value << 6)

		if len(self.serienmarker_tags) == 0:
			tags = ""
		else:
			tags = json.dumps(self.serienmarker_tags)

		self.database.setMarkerSettings(self.serien_id, (self.savetopath.value, int(Staffelverzeichnis), Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen,
		AufnahmezeitVon, AufnahmezeitBis, int(self.preferredChannel.value), int(self.useAlternativeChannel.value),
		vpsSettings, excludedWeekdays, tags, int(self.addToDatabase.value), updateFromEPG, skipSeriesServer, autoAdjust, self.epgSeriesName.value, kindOfTimer, forceRecording))

		self.close(True)

	def cancel(self):
		self.close(False)


