import QtQuick

Item {
    id: root
    width: 180
    height: 120

    Text {
        id: zzz
        anchors.horizontalCenter: parent.horizontalCenter
        text: "Z  z  z"
        color: "#bfefff"
        font.pixelSize: 38
        font.bold: true
        style: Text.Outline
        styleColor: "#145a70"

        SequentialAnimation on y {
            loops: Animation.Infinite
            NumberAnimation { from: 72; to: 22; duration: 1800; easing.type: Easing.InOutSine }
            PauseAnimation { duration: 250 }
            PropertyAction { value: 72 }
        }
        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { from: 0; to: 1; duration: 420 }
            PauseAnimation { duration: 850 }
            NumberAnimation { from: 1; to: 0; duration: 530 }
            PauseAnimation { duration: 250 }
        }
    }
}
