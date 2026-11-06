package client

import java.awt.*
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.Socket
import java.util.*
import javax.swing.*

/**
 * Cliente Desktop GUI implementado en Kotlin usando Swing nativo.
 * Se comunica con el Nodo Backend exclusivamente mediante Sockets TCP propios del SDK estándar.
 * Sin WebSockets, sin librerías externas de mensajería.
 */
class DesktopChatApp : JFrame("Cliente Desktop Kotlin - Chat de Diagnostico CNN") {

    private val hostField = JTextField("localhost", 10)
    private val portField = JTextField("9000", 5)
    private val clientField = JTextField("CLI_KOTLIN_DESK_01", 15)
    private val tokenField = JTextField("TOKEN_KOTLIN_DESK_9921", 18)
    private val connectBtn = JButton("Conectar TCP")

    private val chatArea = JTextArea(15, 45)
    private val statusLabel = JLabel("Estado: Desconectado")
    private val modelSelector = JComboBox(arrayOf("MODELO_A (Chest X-Ray)"))
    private val sendNormalBtn = JButton("Enviar Rx Normal")
    private val sendPneumoniaBtn = JButton("Enviar Rx Neumonia")

    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private var reader: BufferedReader? = null
    private var isConnected = false

    init {
        defaultCloseOperation = EXIT_ON_CLOSE
        setSize(700, 520)
        setLocationRelativeTo(null)
        layout = BorderLayout(8, 8)

        // Panel Superior: Conexión TCP
        val topPanel = JPanel(FlowLayout(FlowLayout.LEFT))
        topPanel.background = Color(30, 41, 59)
        topPanel.add(JLabel("Host:").apply { foreground = Color.WHITE })
        topPanel.add(hostField)
        topPanel.add(JLabel("Puerto:").apply { foreground = Color.WHITE })
        topPanel.add(portField)
        topPanel.add(JLabel("Cliente:").apply { foreground = Color.WHITE })
        topPanel.add(clientField)
        topPanel.add(connectBtn)
        add(topPanel, BorderLayout.NORTH)

        // Área Central: Chat
        chatArea.isEditable = false
        chatArea.background = Color(15, 23, 42)
        chatArea.foreground = Color(241, 245, 249)
        chatArea.font = Font("Consolas", Font.PLAIN, 13)
        val scrollPane = JScrollPane(chatArea)
        add(scrollPane, BorderLayout.CENTER)

        // Panel Inferior: Controles de Envío
        val bottomPanel = JPanel(BorderLayout(5, 5))
        bottomPanel.background = Color(30, 41, 59)

        val controlsPanel = JPanel(FlowLayout(FlowLayout.LEFT))
        controlsPanel.background = Color(30, 41, 59)
        controlsPanel.add(JLabel("Token:").apply { foreground = Color.WHITE })
        controlsPanel.add(tokenField)
        controlsPanel.add(JLabel("Modelo:").apply { foreground = Color.WHITE })
        controlsPanel.add(modelSelector)
        controlsPanel.add(sendNormalBtn)
        controlsPanel.add(sendPneumoniaBtn)

        val statusPanel = JPanel(FlowLayout(FlowLayout.LEFT))
        statusPanel.background = Color(15, 23, 42)
        statusLabel.foreground = Color(148, 163, 184)
        statusPanel.add(statusLabel)

        bottomPanel.add(controlsPanel, BorderLayout.NORTH)
        bottomPanel.add(statusPanel, BorderLayout.SOUTH)
        add(bottomPanel, BorderLayout.SOUTH)

        // Listeners
        connectBtn.addActionListener { toggleConnection() }
        sendNormalBtn.addActionListener { sendXRay(0) }
        sendPneumoniaBtn.addActionListener { sendXRay(1) }
    }

    private fun appendLog(msg: String) {
        SwingUtilities.invokeLater {
            chatArea.append(msg + "\n")
            chatArea.caretPosition = chatArea.document.length
        }
    }

    private fun toggleConnection() {
        if (!isConnected) {
            try {
                val host = hostField.text.trim()
                val port = portField.text.trim().toInt()
                socket = Socket(host, port)
                writer = PrintWriter(socket!!.getOutputStream(), true)
                reader = BufferedReader(InputStreamReader(socket!!.getInputStream()))
                isConnected = true
                connectBtn.text = "Desconectar"
                statusLabel.text = "Estado: Conectado a $host:$port (Sockets TCP puros)"
                appendLog("[+] Conexión establecida con Nodo Backend en $host:$port")

                // Hilo receptor de respuestas del servidor
                Thread {
                    try {
                        var line: String?
                        while (reader?.readLine().also { line = it } != null) {
                            appendLog("<<< Respuesta del Sistema:\n$line\n-----------------------------")
                        }
                    } catch (e: Exception) {
                        appendLog("[-] Conexión cerrada por el servidor.")
                    } finally {
                        closeConnection()
                    }
                }.start()

            } catch (e: Exception) {
                JOptionPane.showMessageDialog(this, "Error conectando al socket: ${e.message}", "Error TCP", JOptionPane.ERROR_MESSAGE)
            }
        } else {
            closeConnection()
        }
    }

    private fun closeConnection() {
        try {
            socket?.close()
        } catch (_: Exception) {}
        isConnected = false
        SwingUtilities.invokeLater {
            connectBtn.text = "Conectar TCP"
            statusLabel.text = "Estado: Desconectado"
        }
    }

    private fun sendXRay(labelType: Int) {
        if (!isConnected || writer == null) {
            JOptionPane.showMessageDialog(this, "Debe conectar primero el Socket TCP.", "Aviso", JOptionPane.WARNING_MESSAGE)
            return
        }

        val tipoStr = if (labelType == 0) "Rx Normal" else "Rx Neumonía (Opacidad)"
        appendLog(">>> Enviando muestra radiológica: $tipoStr...")

        // Generar 784 bytes (28x28) simulando imagen
        val bytes = ByteArray(28 * 28)
        val rand = Random()
        for (i in bytes.indices) {
            var v = 40 + rand.nextInt(30)
            if (labelType == 1 && i > 300 && i < 500) {
                v += 150 // Mancha de opacidad alta
            }
            bytes[i] = v.coerceIn(0, 255).toByte()
        }
        val b64 = Base64.getEncoder().encodeToString(bytes)

        val idSol = "REQ-KT-" + UUID.randomUUID().toString().substring(0, 8)
        val jsonPayload = """
            {
              "idSolicitud": "$idSol",
              "idCliente": "${clientField.text.trim()}",
              "token": "${tokenField.text.trim()}",
              "tipoConsulta": "DIAGNOSTICO",
              "modeloDestino": "MODELO_A",
              "formato": "GRAYSCALE_28X28",
              "imagenB64": "$b64",
              "timestamp": ${System.currentTimeMillis()}
            }
        """.trimIndent().replace("\n", "").replace("\r", "")

        writer?.println(jsonPayload)
    }

    companion object {
        @JvmStatic
        fun main(args: Array<String>) {
            SwingUtilities.invokeLater {
                DesktopChatApp().isVisible = true
            }
        }
    }
}
