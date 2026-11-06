import pika

try:
    c = pika.BlockingConnection(pika.ConnectionParameters("127.0.0.1", 5672))
    print("SUCCESS: Connected to RabbitMQ inside WSL! isOpen =", c.is_open)
    c.close()
except Exception as e:
    print("ERROR inside WSL:", e)
