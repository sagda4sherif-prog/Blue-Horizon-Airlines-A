from copy import deepcopy


class EpisodicBuffer:
    def __init__(self, max_size=20):
        self.max_size = max_size
        self.memories = []

    def add(self, episode):
        self.memories.append(deepcopy(episode))

        if len(self.memories) > self.max_size:
            self.memories.pop(0)

    def get(self):
        return deepcopy(self.memories)

    def clear(self):
        self.memories.clear()


class ReflexionAgent:
    def __init__(
        self,
        planner,
        executor,
        max_trials=3,
        memory_size=20,
    ):
        self.planner = planner
        self.executor = executor
        self.max_trials = max_trials
        self.memory = EpisodicBuffer(memory_size)

    def run(self, request):
        trials = []

        for trial in range(1, self.max_trials + 1):
            previous_lessons = self.memory.get()

            plan = self.planner(
                request=request,
                previous_lessons=previous_lessons,
            )

            result = self.executor(plan)

            episode = {
                "trial": trial,
                "request": request,
                "plan": deepcopy(plan),
                "result": deepcopy(result),
            }

            if result.get("success", False):
                episode["reflection"] = "Successful execution."
                self.memory.add(episode)
                trials.append(episode)

                return {
                    "success": True,
                    "plan": plan,
                    "trials": trials,
                    "memory": self.memory.get(),
                }

            reflection = self._reflect(plan, result)

            episode["reflection"] = reflection
            self.memory.add(episode)
            trials.append(episode)

        return {
            "success": False,
            "plan": trials[-1]["plan"] if trials else None,
            "trials": trials,
            "memory": self.memory.get(),
        }

    def _reflect(self, plan, result):
        errors = result.get("errors", [])

        if errors:
            return {
                "lesson": "Previous plan failed validation.",
                "errors": errors,
                "avoid": errors,
            }

        return {
            "lesson": "Previous execution failed.",
            "errors": ["Execution failed without detailed errors."],
            "avoid": [],
        }
