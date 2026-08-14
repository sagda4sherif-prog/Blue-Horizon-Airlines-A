from planning_eval.runner import EvaluationRunner


def test_evaluation_runner(tmp_path):
    def planner(request):
        return {
            "success": True,
            "plan": request,
        }

    output = tmp_path / "results.json"

    runner = EvaluationRunner(
        planner=planner,
        output_path=str(output),
    )

    result = runner.run()

    assert output.exists()
    assert "scenarios" in result
    assert "summary" in result
    assert len(result["scenarios"]) > 0
