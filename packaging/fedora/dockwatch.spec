Name:           dockwatch
Version:        %{?ver}%{!?ver:0.3.0}
Release:        1%{?dist}
Summary:        Live port map of your docking station and laptop
License:        MIT
URL:            https://github.com/Watashik/DockWatch
Source0:        dockwatch-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3 >= 3.10
Requires:       python3-pyside6
Recommends:     udisks2
Recommends:     pulseaudio-utils
Recommends:     NetworkManager
Recommends:     bluez
Recommends:     power-profiles-daemon

%description
Shows which connectors of the dock and the laptop are in use, what is plugged
in, power and bandwidth, with tray icon, window and terminal views and
plug/unplug notifications. ThinkPad style, works with any laptop.

%prep
%autosetup -n dockwatch-%{version}

%build

%install
sh packaging/stage.sh %{buildroot}

%files
%license LICENSE
%{_bindir}/dockwatch
%{_datadir}/dockwatch/
%{_datadir}/applications/dockwatch.desktop
%{_datadir}/icons/hicolor/scalable/apps/dockwatch.svg
%{_prefix}/lib/udev/rules.d/99-dockwatch.rules
%{_datadir}/licenses/dockwatch/LICENSE
