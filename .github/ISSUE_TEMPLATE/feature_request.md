name: Feature request
description: Suggest a new animation, mobject, or capability
labels: [enhancement]
body:
  - type: markdown
    attributes:
      value: <!-- Thanks for your interest in this project! 🎉 -->

  - type: textarea
    id: problem
    attributes:
      label: What problem does this solve?
      description: Describe the use case or the gap you're running into.
    validations:
      required: true

  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
      description: How would you like it to work? Example Python usage helps a lot.
      render: python

  - type: textarea
    id: spec_sketch
    attributes:
      label: How should scene_data change? (optional)
      description: >
        If this feature adds new animations or mobjects, the JSON emitted in
        `widget.scene_data` will likely need new fields or commands.
        Sketch what those additions might look like here — even rough pseudoJSON is helpful.
        Changes must stay backward-compatible, or bump the top-level `version` field.
      render: json

  - type: dropdown
    id: willing
    attributes:
      label: Are you willing to open a PR?
      options:
        - "Yes"
        - "Maybe"
        - "No"

  - type: textarea
    id: extra
    attributes:
      label: Anything else?
