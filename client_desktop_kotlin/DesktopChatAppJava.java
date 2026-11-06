package client;

import javax.swing.*;
import java.awt.*;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.Socket;
import java.util.Base64;
import java.util.Random;
import java.util.UUID;

/**
 * Cliente Desktop GUI nativo compatible con Java/Kotlin Runtime.
 * Utiliza Sockets TCP puros del SDK estándar.
 */
public class DesktopChatAppJava extends JFrame {

    private final JTextField hostField = new JTextField("localhost", 10);
    private final JTextField portField = new JTextField("9000", 5);
    private final JTextField clientField = new JTextField("CLI_KOTLIN_DESK_01", 15);
    private final JTextField tokenField = new JTextField("TOKEN_KOTLIN_DESK_9921", 18);
    private final JButton connectBtn = new JButton("Conectar TCP");

    private final JTextArea chatArea = new JTextArea(15, 45);
    private final JLabel statusLabel = new JLabel("Estado: Desconectado");
    private final JComboBox<String> modelSelector = new JComboBox<>(new String[]{"MODELO_A (Chest X-Ray)"});
    private final JButton sendNormalBtn = new JButton("Enviar Rx Normal");
    private final JButton sendPneumoniaBtn = new JButton("Enviar Rx Neumonia");

    private Socket socket;
    private PrintWriter writer;
    private BufferedReader reader;
    private boolean isConnected = false;

    public DesktopChatAppJava() {
        super("Cliente Desktop - Chat de Diagnostico CNN (Sockets TCP)");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(720, 530);
        setLocationRelativeTo(null);
        setLayout(new BorderLayout(8, 8));

        // Panel Superior: Conexión TCP
        JPanel topPanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
        topPanel.setBackground(new Color(30, 41, 59));
        JLabel lblHost = new JLabel("Host:"); lblHost.setForeground(Color.WHITE); topPanel.add(lblHost);
        topPanel.add(hostField);
        JLabel lblPort = new JLabel("Puerto:"); lblPort.setForeground(Color.WHITE); topPanel.add(lblPort);
        topPanel.add(portField);
        JLabel lblCli = new JLabel("Cliente:"); lblCli.setForeground(Color.WHITE); topPanel.add(lblCli);
        topPanel.add(clientField);
        topPanel.add(connectBtn);
        add(topPanel, BorderLayout.NORTH);

        // Área Central: Chat
        chatArea.setEditable(false);
        chatArea.setBackground(new Color(15, 23, 42));
        chatArea.setForeground(new Color(241, 245, 249));
        chatArea.setFont(new Font("Consolas", Font.PLAIN, 13));
        JScrollPane scrollPane = new JScrollPane(chatArea);
        add(scrollPane, BorderLayout.CENTER);

        // Panel Inferior: Controles
        JPanel bottomPanel = new JPanel(new BorderLayout(5, 5));
        bottomPanel.setBackground(new Color(30, 41, 59));

        JPanel controlsPanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
        controlsPanel.setBackground(new Color(30, 41, 59));
        JLabel lblTok = new JLabel("Token:"); lblTok.setForeground(Color.WHITE); controlsPanel.add(lblTok);
        controlsPanel.add(tokenField);
        JLabel lblMod = new JLabel("Modelo:"); lblMod.setForeground(Color.WHITE); controlsPanel.add(lblMod);
        controlsPanel.add(modelSelector);
        controlsPanel.add(sendNormalBtn);
        controlsPanel.add(sendPneumoniaBtn);

        JPanel statusPanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
        statusPanel.setBackground(new Color(15, 23, 42));
        statusLabel.setForeground(new Color(148, 163, 184));
        statusPanel.add(statusLabel);

        bottomPanel.add(controlsPanel, BorderLayout.NORTH);
        bottomPanel.add(statusPanel, BorderLayout.SOUTH);
        add(bottomPanel, BorderLayout.SOUTH);

        connectBtn.addActionListener(e -> toggleConnection());
        sendNormalBtn.addActionListener(e -> sendXRay(0));
        sendPneumoniaBtn.addActionListener(e -> sendXRay(1));
    }

    private void appendLog(String msg) {
        SwingUtilities.invokeLater(() -> {
            chatArea.append(msg + "\n");
            chatArea.setCaretPosition(chatArea.getDocument().getLength());
        });
    }

    private void toggleConnection() {
        if (!isConnected) {
            try {
                String host = hostField.getText().trim();
                int port = Integer.parseInt(portField.getText().trim());
                socket = new Socket(host, port);
                writer = new PrintWriter(socket.getOutputStream(), true);
                reader = new BufferedReader(new InputStreamReader(socket.getInputStream()));
                isConnected = true;
                connectBtn.setText("Desconectar");
                statusLabel.setText("Estado: Conectado a " + host + ":" + port + " (Sockets TCP puros)");
                appendLog("[+] Conexión establecida con Nodo Backend en " + host + ":" + port);

                new Thread(() -> {
                    try {
                        String line;
                        while ((line = reader.readLine()) != null) {
                            appendLog("<<< Respuesta del Sistema:\n" + line + "\n-----------------------------");
                        }
                    } catch (Exception ex) {
                        appendLog("[-] Conexión cerrada.");
                    } finally {
                        closeConnection();
                    }
                }).start();

            } catch (Exception ex) {
                JOptionPane.showMessageDialog(this, "Error conectando: " + ex.getMessage(), "Error TCP", JOptionPane.ERROR_MESSAGE);
            }
        } else {
            closeConnection();
        }
    }

    private void closeConnection() {
        try {
            if (socket != null) socket.close();
        } catch (Exception ignored) {}
        isConnected = false;
        SwingUtilities.invokeLater(() -> {
            connectBtn.setText("Conectar TCP");
            statusLabel.setText("Estado: Desconectado");
        });
    }

    private void sendXRay(int labelType) {
        if (!isConnected || writer == null) {
            JOptionPane.showMessageDialog(this, "Debe conectar primero el Socket TCP.", "Aviso", JOptionPane.WARNING_MESSAGE);
            return;
        }

        String tipoStr = (labelType == 0) ? "Rx Normal" : "Rx Neumonía (Opacidad)";
        appendLog(">>> Enviando radiografía de tórax: " + tipoStr + "...");

        byte[] bytes = new byte[28 * 28];
        Random rand = new Random();
        for (int i = 0; i < bytes.length; i++) {
            int v = 40 + rand.nextInt(30);
            if (labelType == 1 && i > 300 && i < 500) {
                v += 150;
            }
            bytes[i] = (byte) Math.min(255, Math.max(0, v));
        }
        String b64 = Base64.getEncoder().encodeToString(bytes);
        String idSol = "REQ-DESK-" + UUID.randomUUID().toString().substring(0, 8);

        String jsonPayload = String.format(
            "{\"idSolicitud\":\"%s\",\"idCliente\":\"%s\",\"token\":\"%s\",\"tipoConsulta\":\"DIAGNOSTICO\",\"modeloDestino\":\"MODELO_A\",\"formato\":\"GRAYSCALE_28X28\",\"imagenB64\":\"%s\",\"timestamp\":%d}",
            idSol, clientField.getText().trim(), tokenField.getText().trim(), b64, System.currentTimeMillis()
        );

        writer.println(jsonPayload);
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new DesktopChatAppJava().setVisible(true));
    }
}
