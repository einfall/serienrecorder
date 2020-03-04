Handlebars.registerHelper('if_isactive', function(condition, options) {
    if(document.title.indexOf(condition) > -1) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});
var template = Handlebars.templates['sidebar-nav-template.hbr'];
var data =
{   menus: [
    {href: "index.htm", title: "Einleitung", submenus: [
        { href: "index.htm#installation", title: "Installation"},
        { href: "index.htm#erste_schritte", title: "Erste Schritte"},
        { href: "index.htm#einstellungen", title: "Globale Einstellungen"},
        { href: "index.htm#autocheck", title: "Autocheck (AC, Suchlauf)"},
        { href: "index.htm#hilfe", title: "Hilfe"}
    ]},
    {href: "einstellungen.htm", title: "Globale Einstellungen", submenus: [
        { href: "einstellungen.htm#system", title: "System"},
        { href: "einstellungen.htm#autocheck", title: "AutoCheck"},
        { href: "einstellungen.htm#timer", title: "Timer"},
        { href: "einstellungen.htm#optimierungen", title: "Optimierungen"},
        { href: "einstellungen.htm#gui", title: "GUI"},
        { href: "einstellungen.htm#log", title: "Log"},
		{ href: "einstellungen.htm#tastatur-ge", title: "Tastaturbelegung"},
    ]},
    {href: "serienplaner.htm", title: "Serien-Planer", submenus: [
        { href: "serienplaner.htm#anzeigemodus", title: "Tagesübersicht / TOP30"},
        { href: "serienplaner.htm#sender-zuordnen", title: "Sender zuordnen"},
        { href: "serienplaner.htm#serien-marker", title: "Serien-Marker"},
        { href: "serienplaner.htm#timer-liste", title: "Timer-Liste"},
		{ href: "serienplaner.htm#tastatur-sp", title: "Tastaturbelegung"},
    ]},
	{href: "senderzuordnung.htm", title: "Senderzuordnung",},
	{href: "serienmarker.htm", title: "Serien-Marker", submenus: [
        { href: "serienmarker.htm#deaktivieren", title: "(De) aktivieren/löschen"},
        { href: "serienmarker.htm#sender-auswaehlen", title: "Sender auswählen"},
        { href: "serienmarker.htm#staffel-auswaehlen", title: "Staffel auswählen"},
        { href: "serienmarker.htm#sendetermine", title: "Sendetermine"},
        { href: "serienmarker.htm#timer-liste", title: "Timer-Liste"},
		{ href: "serienmarker.htm#serien-menu", title: "Serien-Marker Menü"},
		{ href: "serienmarker.htm#tastatur-sm", title: "Tastaturbelegung"},
    ]},
	{href: "eiligen.htm", title: "Für die ganz Eiligen",},
	{href: "serie-hinzufügen.htm", title: "Serie/Marker hinzufügen", submenus: [
	    { href: "serie-hinzufügen.htm#filme", title: "Filme"},
	]},
	{href: "suche.htm", title: "Die Suche",},
	{href: "timer-liste.htm", title: "Timer-Liste",},
	{href: "tv-planer-mail.htm", title: "TV-Planer Mail",},
	{href: "sonstige.htm", title: "Sonstige Funktionen", submenus: [
	    { href: "sonstige.htm#cover", title: "Cover"},
        { href: "sonstige.htm#picons", title: "Picons"},
        { href: "sonstige.htm#episodenliste", title: "Episoden-Liste"},
        { href: "sonstige.htm#konfliktliste", title: "Konflikt-Liste"},
        { href: "sonstige.htm#merkzettel", title: "Merkzettel"},
		{ href: "sonstige.htm#serienstarts", title: "Neue Serienstarts"},
		{ href: "sonstige.htm#serienbeschreibung", title: "Serienbeschreibung"},
		{ href: "sonstige.htm#tvdb-id", title: "TVDB-ID ändern/hinzufügen"},
		{ href: "sonstige.htm#vps-plugin", title: "Das VPS-Plugin"},
    ]},
	{href: "faq.htm", title: "FAQ / HGF / WTW",},
	{href: "begriffe.htm", title: "Index",},
	{href: "changelog.htm", title: "Changelog / Updates",},	
]};
var html = template(data);
$('#sidebar-menu').html(html);
