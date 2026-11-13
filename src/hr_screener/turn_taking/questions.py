"""Wording of the yes/no questions the system-one turn-taking model is asked.

The questions are read by a model, like the prompt, so they are English for every call (the
same rule as `prompt_text.py`); only the stop phrases follow the call language, see
`policy.STOP_PHRASES`. Question keys and the machine keys of the state are never localized.
Editing the wording changes `policy.question_set_sha()`, which every call records.

Why the wording is what it is (measured on the Full-Duplex-Bench samples, see
`evals/turn_taking/reports/SUMMARY.md`): finished statements count as complete (they scored
0.2-0.4 with a "question, command or answer" wording), the assistant is the default listener
(cold starts were scored "not addressed"), and polite topic switches ("by the way...") count as
interruptions. `new_request` catches a new question even when `taking_floor` stays low.
"""

SYSTEM_ONE_TEXTS: dict[str, str] = {
    "turn_complete": (
        "The speaker is talking with a voice assistant; the words come from speech "
        "recognition, without punctuation, and may be cut off. Has the speaker finished what "
        "they were saying, so the assistant can respond? A finished question, command, "
        "answer, statement, story point or opinion is complete even if nothing was asked; "
        "trailing off, an unfinished phrase such as 'so what I want to know is', or a pause "
        "for thought is not."
    ),
    "holding_floor": (
        "Is the speaker explicitly asking for more time or asking the assistant to wait, for "
        "example 'hold on, let me type something' or 'give me a second'?"
    ),
    "addressed_to_agent": (
        "This is a conversation with the voice assistant, even if it has just started: "
        "answer yes unless there is clear evidence the speech is meant for someone else, "
        "such as a name or term of address for another person ('Dad', 'honey', 'Mateo'), an "
        "aside to someone in the room, a TV or background voice, or the speaker talking to "
        "themselves. 'Hey, can you hold my coffee?' said to a person is not addressed to the "
        "assistant."
    ),
    "taking_floor": (
        "The assistant is currently speaking. Is the speaker's latest speech a real "
        "interruption that takes the floor (stop, correct, redirect, or ask something new), "
        "including a polite topic switch such as 'by the way...', 'oh, before I forget...' "
        "or 'actually...' followed by a new question, as opposed to a backchannel such as "
        "'right', 'yeah' or 'uh huh' that means keep going? If the assistant is not "
        "speaking, answer no."
    ),
    "new_request": (
        "Is the speaker asking the assistant a new question or making a new request (not "
        "just reacting to what it said)?"
    ),
}
