import QtQuick

Item {
    id: root
    property string faceState: "IDLE"
    property string emotion: "NEUTRAL"
    property real mouthOpen: 0
    property bool blinking: false
    property real lookOffset: 0
    // All facial features use one design coordinate system. Scaling it as a
    // single unit keeps both eyes perfectly equal and prevents the mouth from
    // stretching on ultrawide, 16:10, or small displays.
    readonly property real faceScale: Math.max(0.1, Math.min(width / 800, height / 450) * 0.98)

    Item {
        id: fittedFace
        width: 800
        height: 450
        anchors.centerIn: parent
        scale: root.faceScale
        transformOrigin: Item.Center

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -35
            // Push both eyes outward toward the left/right frame edges while
            // keeping their sizes and center offsets perfectly symmetrical.
            spacing: 250

            Eye { isLeft: true; faceState: root.faceState; emotion: root.emotion; blinking: root.blinking; lookOffset: root.lookOffset; scale: 1.12 }
            Eye { isLeft: false; faceState: root.faceState; emotion: root.emotion; blinking: root.blinking; lookOffset: root.lookOffset; scale: 1.12 }
        }

        Mouth {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: 140
            faceState: root.faceState
            emotion: root.emotion
            mouthOpen: root.mouthOpen
            scale: 1.12
        }

        AngerMark {
            visible: root.emotion === "ANGRY"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.horizontalCenterOffset: 245
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -165
        }

        SleepZzz {
            visible: root.faceState === "SLEEPING"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.horizontalCenterOffset: 270
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -145
        }

        TearDrop {
            visible: root.emotion === "SAD"
            x: parent.width / 2 - 292
            y: parent.height / 2 + 15
        }

        TearDrop {
            visible: root.emotion === "SAD"
            x: parent.width / 2 + 250
            y: parent.height / 2 + 15
        }
    }
}
