class RedisKeys:
    @staticmethod
    def args(workflow: str, function: str, instance_id: str) -> str:
        """STRING — input args for one function invocation."""
        return f"{workflow}-{function}-{instance_id}"

    @staticmethod
    def result(workflow: str, instance_id: str) -> str:
        """STREAM — result written by a function instance."""
        return f"{workflow}-return-{instance_id}"

    @staticmethod
    def descriptor(workflow: str, workflow_id: str) -> str:
        """HASH — all function descriptors for a workflow run, keyed by instance name."""
        return f"{workflow}-descriptor-{workflow_id}"

    @staticmethod
    def properties(workflow: str, function: str) -> str:
        """STRING — shared properties for a function type, same across all instances."""
        return f"{workflow}-{function}-properties"

    @staticmethod
    def group_result(workflow: str, group_id: str) -> str:
        """STREAM — combined results from a flux group of function instances."""
        return f"{workflow}-group-{group_id}"
