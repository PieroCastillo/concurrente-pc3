package com.example.cnnchat

import android.os.Bundle
import android.util.Base64
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.Socket
import java.util.Random
import java.util.UUID

/**
 * Actividad Principal Android: Chat de Diagnóstico CNN.
 * Se comunica con el Nodo Backend exclusivamente mediante Sockets TCP nativos de Java/Kotlin (java.net.Socket).
 * Cumple la restricción: Cero WebSockets, Cero librerías externas.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var etHost: EditText
    private lateinit var etPort: EditText
    private lateinit var btnConnect: Button
    private lateinit var btnSendNormal: Button
    private lateinit var btnSendPneumonia: Button
    private lateinit var tvChat: TextView

    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private var reader: BufferedReader? = null
    private var isConnected = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etHost = findViewById(R.id.etHost)
        etPort = findViewById(R.id.etPort)
        btnConnect = findViewById(R.id.btnConnect)
        btnSendNormal = findViewById(R.id.btnSendNormal)
        btnSendPneumonia = findViewById(R.id.btnSendPneumonia)
        tvChat = findViewById(R.id.tvChat)

        btnConnect.setOnClickListener {
            if (!isConnected) connectTcp() else disconnectTcp()
        }

        btnSendNormal.setOnClickListener { sendDiagnosticRequest(0) }
        btnSendPneumonia.setOnClickListener { sendDiagnosticRequest(1) }
    }

    private fun connectTcp() {
        Thread {
            try {
                val host = etHost.text.toString().trim()
                val port = etPort.text.toString().trim().toInt()
                socket = Socket(host, port)
                writer = PrintWriter(socket!!.getOutputStream(), true)
                reader = BufferedReader(InputStreamReader(socket!!.getInputStream()))
                isConnected = true

                runOnUiThread {
                    btnConnect.text = "Desconectar"
                    appendMessage("Sistema: Conectado a $host:$port vía Socket TCP nativo")
                }

                // Hilo de recepción de mensajes
                var line: String?
                while (reader?.readLine().also { line = it } != null) {
                    val msg = line
                    runOnUiThread {
                        appendMessage("Diagnostico Recibido:\n$msg\n---")
                    }
                }
            } catch (e: Exception) {
                runOnUiThread {
                    appendMessage("Error TCP: ${e.message}")
                    disconnectTcp()
                }
            }
        }.start()
    }

    private fun disconnectTcp() {
        try {
            socket?.close()
        } catch (_: Exception) {}
        isConnected = false
        runOnUiThread {
            btnConnect.text = "Conectar TCP"
            appendMessage("Sistema: Desconectado.")
        }
    }

    private fun sendDiagnosticRequest(labelType: Int) {
        if (!isConnected || writer == null) {
            appendMessage("Aviso: Conecte el socket primero.")
            return
        }

        Thread {
            // Generar matriz 28x28 (784 bytes)
            val bytes = ByteArray(28 * 28)
            val rand = Random()
            for (i in bytes.indices) {
                var v = 40 + rand.nextInt(30)
                if (labelType == 1 && i in 300..500) v += 150
                bytes[i] = v.coerceIn(0, 255).toByte()
            }
            val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            val idSol = "REQ-AND-" + UUID.randomUUID().toString().substring(0, 8)

            val json = JSONObject().apply {
                put("idSolicitud", idSol)
                put("idCliente", "CLI_ANDROID_01")
                put("token", "TOKEN_ANDROID_APP_7741")
                put("tipoConsulta", "DIAGNOSTICO")
                put("modeloDestino", "MODELO_A")
                put("formato", "GRAYSCALE_28X28")
                put("imagenB64", b64)
                put("timestamp", System.currentTimeMillis())
            }

            writer?.println(json.toString())
            runOnUiThread {
                appendMessage("Android: Enviando radiografía (${if (labelType==0) "Normal" else "Neumonia"})...")
            }
        }.start()
    }

    private fun appendMessage(msg: String) {
        tvChat.append("\n$msg\n")
    }
}
