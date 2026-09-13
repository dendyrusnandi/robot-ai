import QtQuick
import QtQuick.Window

Window {
    id: window
    visible: true
    width: appConfig.width
    height: appConfig.height
    visibility: appConfig.fullscreen ? Window.FullScreen : Window.Windowed
    color: "#010509"
    title: "RN AI BOT"

    Face {
        anchors.fill: parent
        faceState: faceController.state
        emotion: faceController.emotion
        mouthOpen: faceController.mouthOpen
        blinking: blinkTimer.blinking
        lookOffset: 0
    }

    Rectangle {
        width: 52
        height: 52
        radius: 26
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 18
        color: settingsMouse.containsMouse ? "#174453" : "#0a222c"
        border.color: "#36cbe8"
        opacity: settingsMouse.containsMouse ? 0.95 : 0.10
        z: 20
        Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Text { anchors.centerIn: parent; text: "⚙"; color: "#d5fbff"; font.pixelSize: 27 }
        MouseArea { id: settingsMouse; anchors.fill: parent; hoverEnabled: true; onClicked: settingsPanel.open() }
    }

    SettingsPanel {
        id: settingsPanel
        onVisibleChanged: if (!visible) hotkeys.forceActiveFocus()
    }

    Text {
        id: statusText
        visible: appConfig.development
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 12
        anchors.bottomMargin: 9
        color: "#6ca5af"
        opacity: statusHover.containsMouse ? 0.38 : 0.15
        font.pixelSize: 9
        text: faceController.state + " · " + faceController.emotion
        z: 10
        Behavior on opacity { NumberAnimation { duration: 180 } }

        MouseArea {
            id: statusHover
            anchors.fill: parent
            anchors.margins: -8
            hoverEnabled: true
        }
    }

    Timer {
        id: blinkTimer
        property bool blinking: false
        interval: blinking ? 125 : 2800 + Math.random() * 2200
        repeat: true
        running: true
        onTriggered: blinking = !blinking
    }

    Timer {
        id: sleepTimer
        interval: Math.max(5, appConfig.idleSleepSeconds) * 1000
        repeat: false
        running: faceController.state === "IDLE" && appConfig.idleSleepSeconds > 0
        onTriggered: faceController.set_state("SLEEPING")
    }

    Item {
        id: hotkeys
        anchors.fill: parent
        focus: true
        Keys.onPressed: event => {
            if (!appConfig.development) return
            if (event.key === Qt.Key_1) faceController.set_state("IDLE")
            else if (event.key === Qt.Key_2) faceController.set_state("LISTENING")
            else if (event.key === Qt.Key_3) faceController.set_state("THINKING")
            else if (event.key === Qt.Key_4) faceController.set_state("SPEAKING")
            else if (event.key === Qt.Key_5) faceController.set_state("VISION")
            else if (event.key === Qt.Key_H) faceController.set_emotion("HAPPY")
            else if (event.key === Qt.Key_C) faceController.set_emotion("CURIOUS")
            else if (event.key === Qt.Key_S) faceController.set_emotion("SAD")
            else if (event.key === Qt.Key_M) faceController.set_emotion("ANGRY")
            else if (event.key === Qt.Key_P) faceController.set_emotion("DIZZY")
            else if (event.key === Qt.Key_U) faceController.set_emotion("SURPRISED")
            else if (event.key === Qt.Key_E) faceController.set_emotion("EXCITED")
            else if (event.key === Qt.Key_Y) faceController.set_emotion("SLEEPY")
            else if (event.key === Qt.Key_N) faceController.set_emotion("NEUTRAL")
            else if (event.key === Qt.Key_Escape) Qt.quit()
        }
    }
}
