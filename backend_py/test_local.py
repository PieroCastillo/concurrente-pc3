import pika

try:
    c = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    print("SUCCESS: RabbitMQ connection established! is_open =", c.is_open)
    c.close()
except Exception as e:
    print("ERROR:", e)
