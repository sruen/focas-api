openapi: 3.1.0
info:
  title: FOCAS Match Analysis API
  version: 1.1.5
  description: >
    Runs the FOCAS evidence pipeline. Odds values are never numerically
    converted. Return rate is used only to route each institution snapshot
    to the matching 89-96 skeleton sheet. The response includes three-direction
    psychological interval audit, opening board audit, topic usage audit, and
    optimal-solution / better-solution structure.
servers:
  - url: https://focas-api.onrender.com

paths:
  /v1/analyze:
    post:
      operationId: analyzeFocasMatch
      summary: Analyze a football match with FOCAS
      description: >
        Submit normalized match facts, market narratives, and institution odds.
        Always call this operation before explaining institution motives or
        giving a structural direction. GPT must not invent skeleton intervals;
        it must use the returned audit fields.
      x-openai-isConsequential: false
      security:
        - FocasApiKey: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/FocasAnalyzeRequest"
      responses:
        "200":
          description: FOCAS structured evidence response
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/FocasAnalyzeResponse"
        "400":
          description: Invalid match input
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"
        "401":
          description: Invalid API key
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

components:
  securitySchemes:
    FocasApiKey:
      type: http
      scheme: bearer
  schemas:
    FocasAnalyzeRequest:
      type: object
      required:
        - match
        - home_context
        - away_context
        - h2h
        - strength
        - natural_pulls
        - odds
      properties:
        include_report:
          type: boolean
          default: false
          description: Return the long Markdown report only when the user requests it.
        match:
          $ref: "#/components/schemas/Match"
        home_context:
          $ref: "#/components/schemas/TeamContext"
        away_context:
          $ref: "#/components/schemas/TeamContext"
        h2h:
          $ref: "#/components/schemas/H2HContext"
        strength:
          $ref: "#/components/schemas/StrengthContext"
        natural_pulls:
          type: array
          items:
            $ref: "#/components/schemas/NaturalPull"
        narrative_materials:
          type: array
          items:
            $ref: "#/components/schemas/NarrativeMaterial"
        original_book_mode:
          $ref: "#/components/schemas/OriginalBookMode"
        odds:
          type: array
          minItems: 3
          items:
            $ref: "#/components/schemas/CompanyOdds"
      additionalProperties: true

    Match:
      type: object
      required:
        - home_team
        - away_team
      properties:
        home_team:
          type: string
        away_team:
          type: string
        competition:
          type: string
        kickoff_time:
          type: string
        stage:
          type: string
        neutral_venue:
          type: boolean
        single_leg:
          type: boolean
        match_type:
          type: string
        extra_time_or_penalties:
          type: string
        real_home_away:
          type: boolean
        attention_level:
          type: string
        league_for_table:
          type: string
      additionalProperties: true

    TeamContext:
      type: object
      required:
        - name
        - rank
        - points
        - recent_matches
      properties:
        name:
          type: string
        rank:
          type: string
          description: Ranking context. For national teams, use FIFA ranking, for example "FIFA第20，1620.81分".
        points:
          type: string
          description: Points context. For national teams or friendlies, do not leave empty; use FIFA ranking points or official group/table points.
        recent_matches:
          type: array
          minItems: 5
          description: At least five pre-match results. Each item must start with W, D, or L so the engine can parse recent form.
          items:
            type: string
            pattern: "^[WDL]\\s+.+"
        venue_adaptation:
          type: string
        attack_state:
          type: string
        defense_state:
          type: string
        injuries:
          type: string
        schedule_fatigue:
          type: string
        motivation:
          type: string
        popularity_story:
          type: string
        major_recent_matches:
          type: string
      additionalProperties: true

    H2HContext:
      type: object
      properties:
        overall:
          type: string
        recent_years:
          type: string
        same_competition:
          type: string
        venue_specific:
          type: string
        latest_key_match:
          type: string
        market_psychology:
          type: string
      additionalProperties: true

    StrengthContext:
      type: object
      properties:
        home_grade:
          type: string
          enum:
            - 下游
            - 中下
            - 中游
            - 中上
            - 中强
            - 准强
            - 普强
            - 人强
        away_grade:
          type: string
          enum:
            - 下游
            - 中下
            - 中游
            - 中上
            - 中强
            - 准强
            - 普强
            - 人强
        static_gap:
          type: string
        dynamic_adjustment:
          type: string
        final_gap:
          type: string
        original_distribution:
          type: string
        theoretical_psychological_interval:
          type: string
        theoretical_home_odds_range:
          type: string
        theoretical_draw_odds_reference:
          type: string
        theoretical_away_odds_reference:
          type: string
      additionalProperties: true

    NaturalPull:
      type: object
      required:
        - direction
      properties:
        direction:
          type: string
          enum:
            - 主胜
            - 平局
            - 客胜
          description: Must be exactly one of 主胜, 平局, 客胜.
        strength:
          type: string
          description: strong, medium, weak, or equivalent Chinese text.
        facts:
          type: string
        market_psychology:
          type: string
        popularity_direction:
          type: string
        easy_to_receive:
          type: boolean
        first_eye_direction:
          type: boolean
      additionalProperties: false

    NarrativeMaterial:
      type: object
      required:
        - direction
        - topic
      properties:
        direction:
          type: string
        topic:
          type: string
        category:
          type: string
        facts:
          type: string
        source:
          type: string
        published_at:
          type: string
        visibility:
          type: string
        strength:
          type: string
        strength_alignment:
          type: string
        institution_use_status:
          type: string
        institution_use_evidence:
          type: array
          items:
            type: string
        utilization_mode:
          type: string
      additionalProperties: false

    OriginalBookMode:
      type: object
      properties:
        mode:
          type: string
        reason:
          type: string
        key_odds_to_watch:
          type: string
        easiest_misread:
          type: string
        source_classification:
          type: array
          items:
            type: string
      additionalProperties: true

    CompanyOdds:
      type: object
      required:
        - company
        - initial
        - current
      properties:
        company:
          type: string
          enum:
            - William
            - Ladbrokes
            - Avg
        initial:
          $ref: "#/components/schemas/OddsSnapshot"
        current:
          $ref: "#/components/schemas/OddsSnapshot"
      additionalProperties: false

    OddsSnapshot:
      type: object
      required:
        - home
        - draw
        - away
      properties:
        home:
          type: number
        draw:
          type: number
        away:
          type: number
      additionalProperties: false

    FocasAnalyzeResponse:
      type: object
      properties:
        api_schema_version:
          type: string
        engine_version:
          type: string
        analysis_contract:
          $ref: "#/components/schemas/FreeformObject"
        gpt_execution_gate:
          $ref: "#/components/schemas/FreeformObject"
          description: Mandatory GPT reading order and output gate. GPT must read final_structure_judgement last.
        movement_contradiction_audit:
          type: array
          description: Direction-level contradictions between market pull, topic usage, and odds movement. GPT must explain every item before final judgement.
          items:
            $ref: "#/components/schemas/FreeformObject"
        match:
          $ref: "#/components/schemas/FreeformObject"
        status:
          $ref: "#/components/schemas/FreeformObject"
        expected_opening_interval:
          $ref: "#/components/schemas/FreeformObject"
        strength_dynamic_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Original-book broad-strength grades, dynamic adjustment, final gap, low-side route and interval. GPT must not invent grades.
        original_distribution_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Pre-odds original distribution type, three-direction pressures, first-eye direction and scenario constraints.
        system_routes:
          type: array
          items:
            $ref: "#/components/schemas/FreeformObject"
        skeleton_system_audit:
          type: array
          items:
            $ref: "#/components/schemas/FreeformObject"
        opening_skeleton_audits:
          type: array
          items:
            $ref: "#/components/schemas/FreeformObject"
        psychological_interval_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Three-direction theoretical psychological intervals read from the detected 89-96 system sheets.
        opening_board_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: William / Ladbrokes opening home-draw-away board compared against the table interval.
        pre_odds_predicted_odds_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Exact predicted development odds audit. GPT must not generate exact odds unless calculation_status is FORMULA_CONFIRMED.
        three_direction_development_matrix:
          type: array
          description: Home/draw/away optimal development matrix with predicted odds gate, actual odds, adoption status and conclusion.
          items:
            $ref: "#/components/schemas/FreeformObject"
        fundamental_topic_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: "Structured pre-odds fundamental topics: form, H2H, venue, injuries, motivation, ranking and reputation."
        market_pull_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Three-direction market pull percentages. Percentages are pull share, not match probability.
        optimal_solution_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Counterfactual optimal-solution simulation for home, draw, and away scenarios.
        bookmaker_topic_usage_audit:
          $ref: "#/components/schemas/FreeformObject"
          description: Audit of available topics, used topics, unused topics, and utilization mode.
        future_adjustment_plan:
          $ref: "#/components/schemas/FreeformObject"
          description: Expected later bookmaker adjustment path if an optimal or better solution exists.
        final_structure_judgement:
          $ref: "#/components/schemas/FreeformObject"
          description: "Final structural status: EXECUTE, LEAN, BETTER_SOLUTION_ONLY, NO_OPTIMAL_SOLUTION, or NO_BET_STRUCTURE."
        opening_motive_chain:
          type: array
          items:
            $ref: "#/components/schemas/FreeformObject"
        narrative_audit:
          $ref: "#/components/schemas/FreeformObject"
        scenario_audit:
          $ref: "#/components/schemas/FreeformObject"
        opening_interval_audit:
          $ref: "#/components/schemas/FreeformObject"
        notes:
          type: array
          items:
            type: string
        report_markdown:
          type: string
      additionalProperties: true

    FreeformObject:
      type: object
      properties:
        schema_note:
          type: string
          description: Optional placeholder; response objects may include additional FOCAS fields.
      additionalProperties: true

    ErrorResponse:
      type: object
      properties:
        error:
          type: string
        detail:
          type: string
      additionalProperties: true
