class Node:
    def __init__(self, donation_data):
        self.data = donation_data  # Diccionario u objeto de la donación
        self.priority = donation_data.get("priority", 4)
        self.timestamp = donation_data.get("timestamp", datetime.now(timezone.utc).timestamp())
        self.donation_id = donation_data.get("id")
        self.prev = None
        self.next = None


class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None

    def is_empty(self):
        return self.head is None

    def insert_sorted(self, donation_data):
        """Inserta manteniendo el orden de la cola de prioridad:
           1. Menor valor de prioridad primero (1 es mayor urgencia).
           2. A igual prioridad, mayor antigüedad (timestamp menor) primero (FIFO).
        """
        new_node = Node(donation_data)
        
        # Caso 1: Lista vacía
        if self.is_empty():
            self.head = self.tail = new_node
            return

        current = self.head
        while current is not None:
            # Comparamos prioridad y timestamp
            if (new_node.priority < current.priority) or \
               (new_node.priority == current.priority and new_node.timestamp < current.timestamp):
                # Insertar antes de 'current'
                new_node.next = current
                new_node.prev = current.prev
                if current.prev is not None:
                    current.prev.next = new_node
                else:
                    self.head = new_node
                current.prev = new_node
                return
            current = current.next

        # Caso 2: Si es el de menor prioridad, va al final (tail)
        self.tail.next = new_node
        new_node.prev = self.tail
        self.tail = new_node

    def to_list(self):
        """Convierte la lista doble en una lista normal de Python para respuestas JSON."""
        elements = []
        current = self.head
        while current is not None:
            elements.append(current.data)
            current = current.next
        return elements
