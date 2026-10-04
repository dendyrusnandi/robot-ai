import QtQuick

Item {
    id: root
    property bool clockwise: true

    Canvas {
        id: spiral
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.lineWidth = 9
            ctx.lineCap = "round"
            ctx.strokeStyle = "#bdfaff"
            ctx.shadowColor = "#17dfff"
            ctx.shadowBlur = 14
            ctx.beginPath()
            const cx = width / 2
            const cy = height / 2
            for (let i = 0; i <= 90; i++) {
                const angle = i * 0.24
                const radius = 2 + i * 0.62
                const x = cx + Math.cos(angle) * radius
                const y = cy + Math.sin(angle) * radius
                if (i === 0) ctx.moveTo(x, y)
                else ctx.lineTo(x, y)
            }
            ctx.stroke()
        }
    }

    RotationAnimator on rotation {
        from: root.clockwise ? 0 : 360
        to: root.clockwise ? 360 : 0
        duration: 1450
        loops: Animation.Infinite
        running: root.visible
    }
}
