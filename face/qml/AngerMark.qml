import QtQuick

Item {
    id: root
    width: 110
    height: 110

    Text {
        anchors.fill: parent
        text: "#"
        color: "#ff243f"
        font.pixelSize: 94
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        style: Text.Outline
        styleColor: "#7d0014"
    }

    SequentialAnimation on scale {
        running: root.visible
        loops: Animation.Infinite
        NumberAnimation { to: 1.08; duration: 380; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1.0; duration: 380; easing.type: Easing.InOutSine }
    }
}
