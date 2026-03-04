"""CDP (Chrome DevTools Protocol) function execution tools."""

from typing import Any, Dict, List, Optional


def register(ctx):
    """Register CDP function tools."""

    # ─── helpers ───────────────────────────────────────────────────────
    async def _get_tab(instance_id: str):
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return tab

    # ═══════════════════════════════════════════════════════════════════

    @ctx.section_tool("cdp-functions")
    async def list_cdp_commands() -> List[str]:
        """
        List all available CDP Runtime commands for function execution.

        Returns:
            List[str]: List of available CDP command names.
        """
        return await ctx.cdp_function_executor.list_cdp_commands()

    @ctx.section_tool("cdp-functions")
    async def execute_cdp_command(
        instance_id: str,
        command: str,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute any CDP Runtime command with given parameters.

        Args:
            instance_id (str): Browser instance ID.
            command (str): CDP command name (e.g., 'evaluate', 'callFunctionOn').
            params (Dict[str, Any], optional): Command parameters (use snake_case).

        Returns:
            Dict[str, Any]: Command execution result.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return {"success": False, "error": f"Instance not found: {instance_id}"}
        return await ctx.cdp_function_executor.execute_cdp_command(tab, command, params or {})

    @ctx.section_tool("cdp-functions")
    async def get_execution_contexts(instance_id: str) -> List[Dict[str, Any]]:
        """
        Get all available JavaScript execution contexts.

        Args:
            instance_id (str): Browser instance ID.

        Returns:
            List[Dict[str, Any]]: List of execution contexts.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return []
        contexts = await ctx.cdp_function_executor.get_execution_contexts(tab)
        return [
            {
                "id": c.id,
                "name": c.name,
                "origin": c.origin,
                "unique_id": c.unique_id,
                "aux_data": c.aux_data,
            }
            for c in contexts
        ]

    @ctx.section_tool("cdp-functions")
    async def discover_global_functions(
        instance_id: str,
        context_id: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover all global JavaScript functions available in the page.

        Args:
            instance_id (str): Browser instance ID.
            context_id (str, optional): Optional execution context ID.

        Returns:
            List[Dict[str, Any]]: List of discovered functions.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return []
        functions = await ctx.cdp_function_executor.discover_global_functions(tab, context_id)
        result = [
            {
                "name": func.name,
                "path": func.path,
                "signature": func.signature,
                "description": func.description,
            }
            for func in functions
        ]

        file_response = ctx.response_handler.handle_response(
            result,
            fallback_filename_prefix="global_functions",
            metadata={
                "context_id": context_id,
                "function_count": len(result),
                "url": getattr(tab, "url", "unknown"),
            },
        )

        if isinstance(file_response, dict) and "file_path" in file_response:
            return [
                {
                    "name": "LARGE_RESPONSE_SAVED_TO_FILE",
                    "path": "file_storage",
                    "signature": "automatic_file_fallback",
                    "description": f"Response too large ({file_response['estimated_tokens']} tokens), saved to: {file_response['filename']}",
                }
            ]

        return file_response

    @ctx.section_tool("cdp-functions")
    async def discover_object_methods(
        instance_id: str,
        object_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Discover methods of a specific JavaScript object.

        Args:
            instance_id (str): Browser instance ID.
            object_path (str): Path to the object (e.g., 'document', 'window.localStorage').

        Returns:
            List[Dict[str, Any]]: List of discovered methods.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return []
        methods = await ctx.cdp_function_executor.discover_object_methods(tab, object_path)
        methods_data = [
            {
                "name": method.name,
                "path": method.path,
                "signature": method.signature,
                "description": method.description,
            }
            for method in methods
        ]
        return await ctx.response_handler.handle_response(
            methods_data, f"object_methods_{object_path.replace('.', '_')}"
        )

    @ctx.section_tool("cdp-functions")
    async def call_javascript_function(
        instance_id: str,
        function_path: str,
        args: List[Any] = None,
    ) -> Dict[str, Any]:
        """
        Call a JavaScript function with arguments.

        Args:
            instance_id (str): Browser instance ID.
            function_path (str): Full path to the function.
            args (List[Any], optional): Arguments to pass.

        Returns:
            Dict[str, Any]: Function call result.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return {"success": False, "error": f"Instance not found: {instance_id}"}
        return await ctx.cdp_function_executor.call_discovered_function(
            tab, function_path, args or []
        )

    @ctx.section_tool("cdp-functions")
    async def inspect_function_signature(
        instance_id: str,
        function_path: str,
    ) -> Dict[str, Any]:
        """
        Inspect a JavaScript function's signature and details.

        Args:
            instance_id (str): Browser instance ID.
            function_path (str): Full path to the function.

        Returns:
            Dict[str, Any]: Function signature and details.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return {"success": False, "error": f"Instance not found: {instance_id}"}
        return await ctx.cdp_function_executor.inspect_function_signature(tab, function_path)

    @ctx.section_tool("cdp-functions")
    async def inject_and_execute_script(
        instance_id: str,
        script_code: str,
        context_id: str = None,
    ) -> Dict[str, Any]:
        """
        Inject and execute custom JavaScript code.

        Args:
            instance_id (str): Browser instance ID.
            script_code (str): JavaScript code to execute.
            context_id (str, optional): Optional execution context ID.

        Returns:
            Dict[str, Any]: Script execution result.
        """
        tab = await _get_tab(instance_id)
        return await ctx.cdp_function_executor.inject_and_execute_script(
            tab, script_code, context_id
        )

    @ctx.section_tool("cdp-functions")
    async def create_persistent_function(
        instance_id: str,
        function_name: str,
        function_code: str,
    ) -> Dict[str, Any]:
        """
        Create a persistent JavaScript function that survives page reloads.

        Args:
            instance_id (str): Browser instance ID.
            function_name (str): Name for the function.
            function_code (str): JavaScript function code.

        Returns:
            Dict[str, Any]: Function creation result.
        """
        tab = await _get_tab(instance_id)
        return await ctx.cdp_function_executor.create_persistent_function(
            tab, function_name, function_code, instance_id
        )

    @ctx.section_tool("cdp-functions")
    async def execute_function_sequence(
        instance_id: str,
        function_calls: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Execute a sequence of JavaScript function calls.

        Args:
            instance_id (str): Browser instance ID.
            function_calls (List[Dict[str, Any]]): List of calls with 'function_path', 'args', optional 'context_id'.

        Returns:
            List[Dict[str, Any]]: List of function call results.
        """
        from cdp_function_executor import FunctionCall

        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return [{"success": False, "error": f"Instance not found: {instance_id}"}]
        calls = [
            FunctionCall(
                function_path=call_data["function_path"],
                args=call_data.get("args", []),
                context_id=call_data.get("context_id"),
            )
            for call_data in function_calls
        ]
        return await ctx.cdp_function_executor.execute_function_sequence(tab, calls)

    @ctx.section_tool("cdp-functions")
    async def create_python_binding(
        instance_id: str,
        binding_name: str,
        python_code: str,
    ) -> Dict[str, Any]:
        """
        Create a binding that allows JavaScript to call Python functions.

        Args:
            instance_id (str): Browser instance ID.
            binding_name (str): Name for the binding.
            python_code (str): Python function code (as string).

        Returns:
            Dict[str, Any]: Binding creation result.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            return {"success": False, "error": f"Instance not found: {instance_id}"}
        try:
            exec_globals = {}
            exec(python_code, exec_globals)
            python_function = None
            for name, obj in exec_globals.items():
                if callable(obj) and not name.startswith("_"):
                    python_function = obj
                    break
            if not python_function:
                return {"success": False, "error": "No function found in Python code"}
            return await ctx.cdp_function_executor.create_python_binding(
                tab, binding_name, python_function
            )
        except Exception as e:
            return {"success": False, "error": f"Failed to create Python function: {str(e)}"}

    @ctx.section_tool("cdp-functions")
    async def execute_python_in_browser(
        instance_id: str,
        python_code: str,
    ) -> Dict[str, Any]:
        """
        Execute Python code by translating it to JavaScript.

        Args:
            instance_id (str): Browser instance ID.
            python_code (str): Python code to translate and execute.

        Returns:
            Dict[str, Any]: Execution result.
        """
        tab = await _get_tab(instance_id)
        return await ctx.cdp_function_executor.execute_python_in_browser(tab, python_code)

    @ctx.section_tool("cdp-functions")
    async def get_function_executor_info(
        instance_id: str = None,
    ) -> Dict[str, Any]:
        """
        Get information about the CDP function executor state.

        Args:
            instance_id (str, optional): Optional browser instance ID.

        Returns:
            Dict[str, Any]: Function executor state and capabilities.
        """
        return await ctx.cdp_function_executor.get_function_executor_info(instance_id)
