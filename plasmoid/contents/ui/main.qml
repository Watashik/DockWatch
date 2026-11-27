// DockWatch — виджет панели Plasma 6: значок дока со счётчиком занятых портов, по клику — список подключённого.
// Данные берёт из `dockwatch json` (раз в 3 с), сама программа должна быть установлена (./install.sh).
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    property var st: ({})
    readonly property string cmd: "sh -c 'PATH=$HOME/.local/bin:$PATH; exec dockwatch json'"
    readonly property color tpRed: "#E2231A"

    toolTipMainText: "DockWatch"
    toolTipSubText: st.total ? (st.busy + " / " + st.total + (st.docked ? " · dock" : "")) : "…"
    preferredRepresentation: compactRepresentation

    P5Support.DataSource {
        id: exec
        engine: "executable"
        onNewData: (source, data) => {
            try { root.st = JSON.parse(data["stdout"]) } catch (e) {}
            disconnectSource(source)
        }
    }
    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: (source, data) => disconnectSource(source)
    }
    Timer {
        interval: 3000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: exec.connectSource(root.cmd)
    }

    compactRepresentation: MouseArea {
        Layout.minimumWidth: row.implicitWidth
        onClicked: root.expanded = !root.expanded
        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 3
            Kirigami.Icon { source: "dockwatch"; Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium; Layout.preferredHeight: width }
            PlasmaComponents.Label {
                text: root.st.busy !== undefined ? root.st.busy : ""
                color: root.st.busy ? root.tpRed : Kirigami.Theme.textColor
                font.bold: true
            }
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        Layout.preferredHeight: Kirigami.Units.gridUnit * 18
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            Layout.fillWidth: true
            PlasmaComponents.Label {
                text: "<i><b>ThinkPad</b></i>"
                textFormat: Text.StyledText
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.4
            }
            Rectangle { width: 7; height: 7; radius: 4; color: root.tpRed; Layout.alignment: Qt.AlignTop }
            Item { Layout.fillWidth: true }
            PlasmaComponents.Label {
                opacity: 0.7
                text: (root.st.laptop || "") + (root.st.docked ? "  ·  " + (root.st.dock || "") : "")
                elide: Text.ElideRight
                Layout.maximumWidth: Kirigami.Units.gridUnit * 14
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: root.tpRed; opacity: 0.6 }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: (root.st.ports || []).filter(p => p.busy).concat((root.st.loose || []).map(t => ({label: "?", items: [t], stats: [""]})))
            delegate: ColumnLayout {
                width: ListView.view.width
                spacing: 0
                RowLayout {
                    Rectangle { width: 8; height: 8; radius: 4; color: modelData.label === "?" ? "#c9a227" : root.tpRed }
                    PlasmaComponents.Label { text: modelData.label; color: root.tpRed; font.bold: true; Layout.preferredWidth: Kirigami.Units.gridUnit * 5 }
                    PlasmaComponents.Label { text: modelData.items.join("  ·  "); elide: Text.ElideRight; Layout.fillWidth: true }
                }
                PlasmaComponents.Label {
                    visible: (modelData.stats || []).join("") !== ""
                    text: (modelData.stats || []).filter(s => s).join("  ·  ")
                    opacity: 0.65
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    leftPadding: Kirigami.Units.gridUnit * 6
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
            PlasmaComponents.Label {
                anchors.centerIn: parent
                visible: parent.count === 0
                opacity: 0.6
                text: "—"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            PlasmaComponents.Label {
                opacity: 0.7
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                text: {
                    const t = (root.st.sensors || {}).temps || {}
                    const f = ((root.st.sensors || {}).fans || [])[0]
                    let parts = Object.keys(t).map(k => k + " " + Math.round(t[k]) + "°")
                    if (f) parts.push("🌀 " + f)
                    return parts.join("  ·  ")
                }
            }
            Item { Layout.fillWidth: true }
            PlasmaComponents.Button {
                icon.name: "dockwatch"
                text: "DockWatch"
                onClicked: runner.connectSource("sh -c 'PATH=$HOME/.local/bin:$PATH; setsid dockwatch >/dev/null 2>&1 &'")
            }
        }
    }
}
