"""Agent nodes for the film script generator."""

# Allow running as a script (no package context) or as a module.
try:
    from .actor import actor_node
    from .critic import critic_node
    from .orchestrator import orchestrator_node, plan_approval_node
except ImportError:
    from actor import actor_node
    from critic import critic_node
    from orchestrator import orchestrator_node, plan_approval_node

__all__ = ["actor_node", "critic_node", "orchestrator_node", "plan_approval_node"]
