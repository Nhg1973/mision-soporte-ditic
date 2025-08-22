# Este archivo es generado automáticamente por el comando 'update_topics'.
# No lo edites manualmente.

TOPIC_HIERARCHY = {
    "Software": [
        "General",
    ],
}

def get_master_topic_list():
    """
    Genera una lista plana de todos los temas y subtemas para el clasificador.
    """
    master_list = []
    for main_topic, sub_topics in TOPIC_HIERARCHY.items():
        master_list.append(main_topic)
        master_list.extend(sub_topics)
    return master_list
