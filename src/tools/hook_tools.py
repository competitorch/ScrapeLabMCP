"""Dynamic hook tools: create, manage, validate network hooks."""

from typing import Any, Dict, List, Optional


def register(ctx):
    """Register dynamic hook tools."""

    @ctx.section_tool("dynamic-hooks")
    async def create_dynamic_hook(
        name: str,
        requirements: Dict[str, Any],
        function_code: str,
        instance_ids: Optional[List[str]] = None,
        priority: int = 100,
    ) -> Dict[str, Any]:
        """
        Create a new dynamic hook with AI-generated Python function.

        Args:
            name (str): Human-readable hook name.
            requirements (Dict[str, Any]): Matching criteria (url_pattern, method, resource_type, custom_condition).
            function_code (str): Python function code that processes requests.
            instance_ids (Optional[List[str]]): Browser instances to apply hook to (all if None).
            priority (int): Hook priority (lower = higher priority).

        Returns:
            Dict[str, Any]: Hook creation result with hook_id.
        """
        return await ctx.dynamic_hook_ai.create_dynamic_hook(
            name=name,
            requirements=requirements,
            function_code=function_code,
            instance_ids=instance_ids,
            priority=priority,
        )

    @ctx.section_tool("dynamic-hooks")
    async def create_simple_dynamic_hook(
        name: str,
        url_pattern: str,
        action: str,
        target_url: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        instance_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a simple dynamic hook using predefined templates.

        Args:
            name (str): Hook name.
            url_pattern (str): URL pattern to match.
            action (str): Action type - 'block', 'redirect', 'add_headers', or 'log'.
            target_url (Optional[str]): Target URL for redirect action.
            custom_headers (Optional[Dict[str, str]]): Headers for add_headers action.
            instance_ids (Optional[List[str]]): Browser instances to apply hook to.

        Returns:
            Dict[str, Any]: Hook creation result.
        """
        return await ctx.dynamic_hook_ai.create_simple_hook(
            name=name,
            url_pattern=url_pattern,
            action=action,
            target_url=target_url,
            custom_headers=custom_headers,
            instance_ids=instance_ids,
        )

    @ctx.section_tool("dynamic-hooks")
    async def list_dynamic_hooks(
        instance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all dynamic hooks.

        Args:
            instance_id (Optional[str]): Optional filter by browser instance.

        Returns:
            Dict[str, Any]: List of hooks with details and statistics.
        """
        return await ctx.dynamic_hook_ai.list_dynamic_hooks(instance_id=instance_id)

    @ctx.section_tool("dynamic-hooks")
    async def get_dynamic_hook_details(hook_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific dynamic hook.

        Args:
            hook_id (str): Hook identifier.

        Returns:
            Dict[str, Any]: Detailed hook information including function code.
        """
        return await ctx.dynamic_hook_ai.get_hook_details(hook_id=hook_id)

    @ctx.section_tool("dynamic-hooks")
    async def remove_dynamic_hook(hook_id: str) -> Dict[str, Any]:
        """
        Remove a dynamic hook.

        Args:
            hook_id (str): Hook identifier to remove.

        Returns:
            Dict[str, Any]: Removal status.
        """
        return await ctx.dynamic_hook_ai.remove_dynamic_hook(hook_id=hook_id)

    @ctx.section_tool("dynamic-hooks")
    def get_hook_documentation(
        section: str = "overview",
    ) -> Dict[str, Any]:
        """
        Get documentation for creating hook functions.

        Args:
            section (str): Documentation section to retrieve:
                - 'overview': Request object structure and HookAction types
                - 'requirements': Hook requirements and matching criteria
                - 'examples': Example hook functions with explanations
                - 'patterns': Common patterns (ad blocking, API proxying, etc.)
                - 'all': Everything combined

        Returns:
            Dict[str, Any]: Requested documentation.
        """
        sections = {
            "overview": ctx.dynamic_hook_ai.get_request_documentation,
            "requirements": ctx.dynamic_hook_ai.get_requirements_documentation,
            "examples": ctx.dynamic_hook_ai.get_hook_examples,
            "patterns": ctx.dynamic_hook_ai.get_common_patterns,
        }
        if section == "all":
            return {k: fn() for k, fn in sections.items()}
        fn = sections.get(section)
        if not fn:
            return {"error": f"Unknown section '{section}'. Use: overview, requirements, examples, patterns, all"}
        return fn()

    @ctx.section_tool("dynamic-hooks")
    def validate_hook_function(function_code: str) -> Dict[str, Any]:
        """
        Validate hook function code for common issues before creating.

        Args:
            function_code (str): Python function code to validate.

        Returns:
            Dict[str, Any]: Validation results with issues and warnings.
        """
        return ctx.dynamic_hook_ai.validate_hook_function(function_code=function_code)
