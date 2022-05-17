import pika

def before_scenario(context, scenario):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()

    output_queue = channel.queue_declare(queue='', exclusive=True).method.queue
    channel.queue_bind(exchange='robot_output', queue=output_queue, routing_key='#')

    context.channel = channel
    context.output_queue = output_queue