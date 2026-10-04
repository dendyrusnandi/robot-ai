import QtQuick

Item {
    id: root
    property string faceState: "IDLE"
    property string emotion: "NEUTRAL"
    property real mouthOpen: 0
    property real animatedOpen: mouthOpen
    width: 240
    height: 100

    Canvas {
        id: mouthCanvas
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.lineWidth = 11
            ctx.strokeStyle = root.faceState === "OFFLINE" ? "#31545c" : "#c9fbff"
            ctx.shadowColor = "#18dfff"
            ctx.shadowBlur = 20

            if (root.faceState === "SPEAKING") {
                const amount = Math.max(0.08, root.animatedOpen)
                const halfWidth = 48 + amount * 34
                const halfHeight = 7 + amount * 35
                const cx = width / 2
                const cy = height / 2 + 5
                ctx.beginPath()
                ctx.moveTo(cx - halfWidth, cy)
                ctx.bezierCurveTo(cx - halfWidth * 0.55, cy - halfHeight,
                                  cx + halfWidth * 0.55, cy - halfHeight,
                                  cx + halfWidth, cy)
                ctx.bezierCurveTo(cx + halfWidth * 0.58, cy + halfHeight,
                                  cx - halfWidth * 0.58, cy + halfHeight,
                                  cx - halfWidth, cy)
                ctx.closePath()
                ctx.fillStyle = "#021017"
                ctx.fill()
                ctx.stroke()

                ctx.shadowBlur = 8
                ctx.lineWidth = 4
                ctx.strokeStyle = "#64eaff"
                ctx.beginPath()
                ctx.moveTo(cx - halfWidth * 0.58, cy + halfHeight * 0.28)
                ctx.quadraticCurveTo(cx, cy + halfHeight * 0.62,
                                     cx + halfWidth * 0.58, cy + halfHeight * 0.28)
                ctx.stroke()
            } else if (root.emotion === "SURPRISED" || root.emotion === "EXCITED") {
                ctx.beginPath()
                ctx.ellipse(width / 2 - 24, height / 2 - 30, 48, 60)
                ctx.fillStyle = "#021017"
                ctx.fill()
                ctx.stroke()
            } else if (root.emotion === "SAD" || root.emotion === "ANGRY") {
                ctx.beginPath()
                ctx.moveTo(20, 62)
                ctx.quadraticCurveTo(width / 2, 12, width - 20, 62)
            } else {
                ctx.beginPath()
                ctx.moveTo(20, 31)
                ctx.quadraticCurveTo(width / 2, 82, width - 20, 31)
            }
            if (root.faceState !== "SPEAKING")
                ctx.stroke()
        }

        Connections {
            target: root
            function onFaceStateChanged() { mouthCanvas.requestPaint() }
            function onEmotionChanged() { mouthCanvas.requestPaint() }
            function onAnimatedOpenChanged() { mouthCanvas.requestPaint() }
        }
    }
}
