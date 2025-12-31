"""
Load Balancer for ComfyUI Servers

Selects the best available server based on queue status.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from .comfyui_client import ComfyUIClient


class ServerHealth:
    """Health status of a ComfyUI server"""

    def __init__(self, address: str):
        self.address = address
        self.is_online = False
        self.queue_running = 0
        self.queue_pending = 0
        self.total_load = 0
        self.last_check = None
        self.error = None

    def update(self):
        """Update server health status"""
        try:
            client = ComfyUIClient(server_address=self.address)

            # Get queue status
            queue = client.get_queue()
            self.queue_running = len(queue.get('queue_running', []))
            self.queue_pending = len(queue.get('queue_pending', []))
            self.total_load = self.queue_running + self.queue_pending

            self.is_online = True
            self.error = None
            self.last_check = datetime.utcnow()

        except Exception as e:
            self.is_online = False
            self.error = str(e)
            self.last_check = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "address": self.address,
            "is_online": self.is_online,
            "queue_running": self.queue_running,
            "queue_pending": self.queue_pending,
            "total_load": self.total_load,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "error": self.error
        }


class LoadBalancer:
    """Load balancer for multiple ComfyUI servers"""

    def __init__(self):
        self.servers: Dict[str, ServerHealth] = {}
        self._round_robin_index = 0

    def register_server(self, address: str):
        """Register a new server"""
        if address not in self.servers:
            self.servers[address] = ServerHealth(address)
            self.servers[address].update()

    def unregister_server(self, address: str):
        """Unregister a server"""
        if address in self.servers:
            del self.servers[address]

    def update_all_servers(self):
        """Update health status for all servers"""
        for server in self.servers.values():
            server.update()

    def get_best_server(self, strategy: str = "least_loaded") -> Optional[str]:
        """
        Get the best available server based on strategy

        Args:
            strategy: Selection strategy
                - "least_loaded": Server with lowest total queue (default)
                - "round_robin": Rotate through servers
                - "random": Random selection

        Returns:
            Server address or None if no servers available
        """
        # Update all servers
        self.update_all_servers()

        # Filter online servers
        online_servers = [s for s in self.servers.values() if s.is_online]

        if not online_servers:
            return None

        if strategy == "least_loaded":
            # Select server with lowest load
            best = min(online_servers, key=lambda s: s.total_load)
            return best.address

        elif strategy == "round_robin":
            # Round-robin through available servers
            if not online_servers:
                return None
            server = online_servers[self._round_robin_index % len(online_servers)]
            self._round_robin_index += 1
            return server.address

        elif strategy == "random":
            import random
            return random.choice(online_servers).address

        else:
            # Default to least loaded
            best = min(online_servers, key=lambda s: s.total_load)
            return best.address

    def get_server_health(self, address: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific server"""
        if address in self.servers:
            self.servers[address].update()
            return self.servers[address].to_dict()
        return None

    def get_all_servers_health(self) -> List[Dict[str, Any]]:
        """Get health status for all servers"""
        self.update_all_servers()
        return [server.to_dict() for server in self.servers.values()]

    def get_available_servers(self) -> List[str]:
        """Get list of all available (online) servers"""
        self.update_all_servers()
        return [s.address for s in self.servers.values() if s.is_online]


# Global load balancer instance
load_balancer = LoadBalancer()
