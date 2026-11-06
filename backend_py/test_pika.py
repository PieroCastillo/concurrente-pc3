import pika

wsl_ip = "192.168.235.12"
print(f"Testing connection to WSL IP: {wsl_ip}:5672...")
try:
    params = pika.ConnectionParameters(host=wsl_ip, port=5672)
    conn = pika.BlockingConnection(params)
    print("SUCCESS: Connected to RabbitMQ at WSL IP! isOpen =", conn.is_open)
    conn.close()
except Exception as e:
    print("FAILED:", e)
