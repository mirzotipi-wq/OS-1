// SPDX-License-Identifier: GPL-2.0-only
// OS-1 Desktop Shell Layout (Phase 7): macOS Sequoia-style Top Menu Bar + Floating Bottom Dock
// Compatible with KDE Plasma 5.27 (Debian 12 bookworm).

// 0. Remove any pre-existing default panels so only OS-1 Top Bar & Dock exist
var existingPanels = panels();
for (var p = 0; p < existingPanels.length; p++) {
    existingPanels[p].remove();
}

// 1. Configure OS-1 Horizon Wallpaper on all desktop containments
var allDesktops = desktops();
for (var i = 0; i < allDesktops.length; i++) {
    var d = allDesktops[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/OS1Horizon/contents/images/1920x1080.png");
    d.writeConfig("FillMode", 2);
}

// 2. Top Menu Bar (28px translucent bar: OS-1 menu, Global App Menu, spacer, System Tray, Clock)
var topBar = new Panel;
topBar.location = "top";
topBar.height = 28;
topBar.floating = false;
topBar.hiding = "none";

var os1Menu = topBar.addWidget("org.kde.plasma.kickoff");
os1Menu.currentConfigGroup = ["General"];
os1Menu.writeConfig("icon", "/usr/share/pixmaps/os1-logo.svg");
os1Menu.writeConfig("favoritesPortedToKAstats", true);

topBar.addWidget("org.kde.plasma.appmenu");
topBar.addWidget("org.kde.plasma.panelspacer");
topBar.addWidget("org.kde.plasma.systemtray");

var clock = topBar.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateDisplayFormat", "BesideTime");
clock.writeConfig("dateFormat", "custom");
clock.writeConfig("customDateFormat", "ddd MMM d");

// 3. Floating Bottom Dock (centered pill dock with pinned OS-1 apps + running indicators + Trash)
var dock = new Panel;
dock.location = "bottom";
dock.height = 56;
dock.alignment = "center";
dock.minimumLength = 420;
dock.maximumLength = 860;
dock.floating = true;
dock.hiding = "none";

var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:firefox-esr.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:org.kde.kate.desktop",
    "applications:org.kde.gwenview.desktop",
    "applications:org.kde.kcalc.desktop",
    "applications:systemsettings.desktop"
]);
tasks.writeConfig("groupingStrategy", 1);
tasks.writeConfig("indicateAudioStreams", true);

dock.addWidget("org.kde.plasma.trash");
