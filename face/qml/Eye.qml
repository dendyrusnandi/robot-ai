import QtQuick

Item {
    id: root
    property string faceState: "IDLE"
    property string emotion: "NEUTRAL"
    property real lookOffset: 0
    property bool blinking: false
    property bool isLeft: false

    width: 250
    height: 210

    Rectangle {
        anchors.centerIn: eye
        width: eye.width + 70
        height: eye.height + 70
        radius: width / 2
        color: "#20cfff"
        opacity: 0.055
    }

    Rectangle {
        anchors.centerIn: eye
        width: eye.width + 38
        height: eye.height + 38
        radius: width / 2
        color: "#25dfff"
        opacity: 0.10
    }

    Rectangle {
        id: eye
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 0
        width: root.emotion === "SURPRISED" || root.emotion === "EXCITED" ? 182 : 160
        height: root.blinking ? 8
              : root.faceState === "SLEEPING" || root.emotion === "SLEEPY" ? 48
              : root.emotion === "HAPPY" ? 96
              : root.emotion === "SAD" ? 112
              : root.emotion === "CURIOUS" ? 160
              : root.emotion === "SURPRISED" || root.emotion === "EXCITED" ? 182
              : root.faceState === "LISTENING" ? 170 : 160
        rotation: root.emotion === "HAPPY" ? (root.isLeft ? -7 : 7)
                : root.emotion === "SAD" ? (root.isLeft ? 10 : -10)
                : root.emotion === "ANGRY" ? (root.isLeft ? -12 : 12) : 0
        radius: height / 2
        color: "transparent"
        border.width: 13
        border.color: root.faceState === "OFFLINE" ? "#31545c"
                    : root.emotion === "ANGRY" ? "#ff7581" : "#d5fbff"
        antialiasing: true

        Behavior on height { NumberAnimation { duration: root.blinking ? 80 : 360; easing.type: Easing.InOutCubic } }
        Behavior on width { NumberAnimation { duration: 380; easing.type: Easing.InOutCubic } }
        Behavior on rotation { NumberAnimation { duration: 420; easing.type: Easing.InOutCubic } }
        Behavior on anchors.verticalCenterOffset { NumberAnimation { duration: 380; easing.type: Easing.InOutCubic } }

        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            radius: width / 2
            color: "transparent"
            border.width: 4
            border.color: "#22dfff"
            opacity: 0.85
        }

        DizzySpiral {
            anchors.centerIn: parent
            width: parent.width - 24
            height: width
            visible: root.emotion === "DIZZY" && !root.blinking
            clockwise: !root.isLeft
        }
    }

}
