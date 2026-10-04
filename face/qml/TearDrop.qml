import QtQuick

Item {
    id: root
    width: 42
    height: 68
    Canvas {
        id: drop
        width: parent.width
        height: parent.height
        opacity: 0
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.fillStyle = "#60dcff"
            ctx.shadowColor = "#1ecbff"
            ctx.shadowBlur = 15
            ctx.beginPath()
            ctx.moveTo(width / 2, 2)
            ctx.bezierCurveTo(width + 5, 38, width - 2, height - 2, width / 2, height - 2)
            ctx.bezierCurveTo(2, height - 2, -5, 38, width / 2, 2)
            ctx.fill()
        }
    }

    SequentialAnimation {
        running: root.visible
        loops: Animation.Infinite
        NumberAnimation { target: drop; property: "y"; from: -10; to: 75; duration: 1250; easing.type: Easing.InQuad }
        PauseAnimation { duration: 350 }
    }
    SequentialAnimation {
        running: root.visible
        loops: Animation.Infinite
        NumberAnimation { target: drop; property: "opacity"; from: 0; to: 0.9; duration: 220 }
        PauseAnimation { duration: 650 }
        NumberAnimation { target: drop; property: "opacity"; to: 0; duration: 380 }
        PauseAnimation { duration: 350 }
    }
}
