"""Agent nodes for the film script generator."""

__all__ = ["actor_node", "critic_node", "orchestrator_node", "plan_approval_node"]


def __getattr__(name: str):
    """Load optional LangGraph nodes only when a caller asks for one."""
    if name == "actor_node":
        from .actor import actor_node
        return actor_node
    if name == "critic_node":
        from .critic import critic_node
        return critic_node
    if name in {"orchestrator_node", "plan_approval_node"}:
        from .orchestrator import orchestrator_node, plan_approval_node
        return orchestrator_node if name == "orchestrator_node" else plan_approval_node
    raise AttributeError(name)
