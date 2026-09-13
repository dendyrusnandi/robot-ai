import QtQuick

Rectangle {
    id: root
    property color glowColor: "#24dfff"
    property real glowRadius: 28
    color: glowColor
    opacity: 0.10
    radius: width / 2
}

