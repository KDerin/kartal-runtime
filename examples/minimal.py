from kartal_runtime import AgentRuntime, ToolSpec, default_policy, evaluate_process


def main() -> None:
    runtime = AgentRuntime(policy=default_policy())
    runtime.register_tool(ToolSpec("multiply", lambda left, right: left * right, risk=0.1))

    run_id = runtime.start_run("Calculate an evidence-backed product")
    evidence_id = runtime.record_evidence(
        run_id,
        content={"left": 6, "right": 7},
        source_uri="urn:example:validated-operands",
    )
    claim_id = runtime.record_claim(
        run_id,
        agent_id="analyst",
        statement="The validated operands may be multiplied.",
        evidence_ids=[evidence_id],
        confidence=0.98,
    )
    execution = runtime.execute_tool(
        run_id,
        agent_id="analyst",
        tool_name="multiply",
        arguments={"left": 6, "right": 7},
        evidence_ids=[evidence_id],
        claim_ids=[claim_id],
    )
    runtime.complete_run(run_id)

    print("result:", execution.value)
    print("head hash:", runtime.graph(run_id).head_hash)
    print("metrics:", evaluate_process(runtime.graph(run_id)).to_dict())


if __name__ == "__main__":
    main()
