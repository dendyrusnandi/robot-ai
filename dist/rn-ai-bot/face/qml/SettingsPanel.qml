import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: panel
    anchors.fill: parent
    color: "#e6000509"
    visible: false
    z: 100
    property var current: settingsController.values
    property string statusText: ""

    function open() {
        current = settingsController.values
        statusText = ""
        apiKey.text = ""
        providerSelect.currentIndex = Math.max(0, providerSelect.find(current.provider))
        language.currentIndex = Math.max(0, language.find(current.language))
        responseStyle.currentIndex = Math.max(0, responseStyle.find(current.responseStyle || "kasual"))
        model.text = (providerSelect.currentText === "openai" ? current.openaiModel : current.geminiModel) || ""
        openaiVoice.currentIndex = Math.max(0, openaiVoice.find(current.openaiVoice || "marin"))
        vad.checked = current.vadEnabled
        vadLevel.text = String(current.vadMinimumLevel)
        noiseRatio.text = String(current.vadNoiseRatio)
        minimumSpeech.text = String(current.minimumSpeechMs)
        silenceRelease.text = String(current.silenceReleaseMs)
        wakeWord.text = current.wakeWord || "RN"
        echoGuard.checked = current.echoGuard
        bargeInMode.currentIndex = current.bargeInMode === "kata_kunci" ? 1 : 0
        cameraDevice.text = current.cameraDevice || "0"
        fullscreen.checked = current.fullscreen
        debugMode.checked = current.debug
        knowledgeEnabled.checked = current.knowledgeEnabled
        knowledgeFolder.text = current.knowledgeFolder || "knowledge"
        visible = true
    }

    MouseArea { anchors.fill: parent }

    Rectangle {
        width: Math.min(parent.width - 32, 720)
        height: Math.min(parent.height - 32, 690)
        anchors.centerIn: parent
        radius: 24
        color: "#07151d"
        border.color: "#247a91"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                Text { text: "PENGATURAN RN AI BOT"; color: "#d5fbff"; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true }
                Button { text: "✕"; onClicked: panel.visible = false }
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                GridLayout {
                    width: Math.max(560, parent.width)
                    columns: 2
                    columnSpacing: 18
                    rowSpacing: 10

                    Text { text: "Provider AI"; color: "#a8dce5" }
                    ComboBox {
                        id: providerSelect
                        Layout.fillWidth: true
                        model: ["gemini", "openai"]
                        Component.onCompleted: currentIndex = Math.max(0, find(current.provider))
                        onActivated: {
                            apiKey.text = ""
                            model.text = (currentText === "openai" ? current.openaiModel : current.geminiModel) || ""
                        }
                    }
                    Text { text: providerSelect.currentText === "openai" ? "OpenAI API Key" : "Gemini API Key"; color: "#a8dce5" }
                    TextField {
                        id: apiKey
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: (providerSelect.currentText === "openai" ? current.openaiApiKeySet : current.apiKeySet)
                            ? "Sudah terpasang — isi hanya untuk mengganti" : "Masukkan API key"
                    }
                    Text { text: "Bahasa default"; color: "#a8dce5" }
                    ComboBox { id: language; Layout.fillWidth: true; model: ["id-ID", "en-US", "ms-MY", "jv-ID", "zh-CN", "ja-JP"]; Component.onCompleted: currentIndex = Math.max(0, find(current.language)) }
                    Text { text: "Gaya jawaban"; color: "#a8dce5" }
                    ComboBox {
                        id: responseStyle
                        Layout.fillWidth: true
                        model: ["kasual", "formal", "profesional", "ramah", "ringkas", "humoris"]
                    }
                    Text { text: providerSelect.currentText === "openai" ? "Model OpenAI Realtime" : "Model Gemini Live"; color: "#a8dce5" }
                    TextField { id: model; Layout.fillWidth: true; text: current.model || "" }
                    Text { text: "Karakter suara OpenAI"; color: providerSelect.currentText === "openai" ? "#a8dce5" : "#52727a" }
                    ComboBox {
                        id: openaiVoice
                        Layout.fillWidth: true
                        enabled: providerSelect.currentText === "openai"
                        model: ["marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"]
                        ToolTip.visible: hovered
                        ToolTip.text: "Marin dan cedar direkomendasikan OpenAI untuk kualitas terbaik"
                    }

                    Text { text: "Filter suara adaptif"; color: "#a8dce5" }
                    Switch { id: vad; checked: current.vadEnabled }
                    Text { text: "Level suara minimum"; color: "#a8dce5" }
                    TextField { id: vadLevel; Layout.fillWidth: true; text: String(current.vadMinimumLevel); validator: IntValidator { bottom: 80; top: 10000 } }
                    Text { text: "Rasio terhadap noise"; color: "#a8dce5" }
                    TextField { id: noiseRatio; Layout.fillWidth: true; text: String(current.vadNoiseRatio); validator: DoubleValidator { bottom: 1.1; top: 8.0 } }
                    Text { text: "Minimal ucapan (ms)"; color: "#a8dce5" }
                    TextField { id: minimumSpeech; Layout.fillWidth: true; text: String(current.minimumSpeechMs); validator: IntValidator { bottom: 80; top: 3000 } }
                    Text { text: "Catatan suasana ramai"; color: "#7caeb8"; font.pixelSize: 12 }
                    Text {
                        Layout.fillWidth: true
                        text: "Rekomendasi: level 450–700, rasio noise 2.8–3.5, dan minimal ucapan 500–700 ms. Nilai lebih tinggi mengurangi respons terhadap suara latar, tetapi pengguna perlu berbicara lebih jelas dan dekat."
                        color: "#7caeb8"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                    Text { text: "Jeda selesai bicara (ms)"; color: "#a8dce5" }
                    TextField { id: silenceRelease; Layout.fillWidth: true; text: String(current.silenceReleaseMs); validator: IntValidator { bottom: 120; top: 5000 } }
                    Text { text: "Kata panggil saat ramai"; color: "#a8dce5" }
                    TextField { id: wakeWord; Layout.fillWidth: true; text: current.wakeWord || "RN" }
                    Text { text: "Cegah echo speaker"; color: "#a8dce5" }
                    Switch { id: echoGuard; checked: current.echoGuard }
                    Text { text: "Mode interupsi"; color: "#a8dce5" }
                    ComboBox {
                        id: bargeInMode
                        Layout.fillWidth: true
                        model: ["enable", "disable"]
                        ToolTip.visible: hovered
                        ToolTip.text: currentText === "enable"
                            ? "Stop, sebentar, atau langsung bicara"
                            : "Hanya kata stop atau sebentar"
                    }

                    Text { text: "Knowledge dokumen"; color: "#a8dce5" }
                    Switch { id: knowledgeEnabled; checked: current.knowledgeEnabled }
                    Text { text: "Folder knowledge"; color: "#a8dce5" }
                    TextField { id: knowledgeFolder; Layout.fillWidth: true; text: current.knowledgeFolder || "knowledge"; placeholderText: "knowledge" }

                    Text { text: "Perangkat kamera"; color: "#a8dce5" }
                    TextField { id: cameraDevice; Layout.fillWidth: true; text: current.cameraDevice || "0"; placeholderText: "0 atau /dev/video0" }
                    Text { text: "Fullscreen"; color: "#a8dce5" }
                    Switch { id: fullscreen; checked: current.fullscreen }
                    Text { text: "Debug log"; color: "#a8dce5" }
                    Switch { id: debugMode; checked: current.debug }
                }
            }

            Text { text: panel.statusText; color: panel.statusText.startsWith("Gagal") ? "#ff7581" : "#72f0bc"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                Button { text: "Batal"; onClicked: panel.visible = false }
                Button {
                    text: "Simpan"
                    highlighted: true
                    onClicked: panel.statusText = settingsController.save({
                        provider: providerSelect.currentText,
                        apiKey: apiKey.text, language: language.currentText, model: model.text,
                        responseStyle: responseStyle.currentText,
                        openaiVoice: openaiVoice.currentText,
                        vadEnabled: vad.checked, vadMinimumLevel: vadLevel.text,
                        vadNoiseRatio: noiseRatio.text, minimumSpeechMs: minimumSpeech.text,
                        silenceReleaseMs: silenceRelease.text, wakeWord: wakeWord.text,
                        echoGuard: echoGuard.checked,
                        bargeInMode: bargeInMode.currentText === "enable" ? "bebas" : "kata_kunci",
                        cameraDevice: cameraDevice.text, fullscreen: fullscreen.checked,
                        debug: debugMode.checked, knowledgeEnabled: knowledgeEnabled.checked,
                        knowledgeFolder: knowledgeFolder.text
                    })
                }
            }
        }
    }
}
