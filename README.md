# SkillCorner X PySport Analytics Cup
This repository contains [Emaly Vatne's](https://emalyvatne.github.io/) submission for the SkillCorner X PySport Analytics Cup **Research Track**.

## Contextualizing Worst-Case Scenario Running Demands by Identifying Associated In-Game Events and Movement Sequences in Soccer to Inform Physical Preparation and Tactical Development

### Introduction  
External load metrics derived from match play are ubiquitously used to support physical preparation in soccer (REF). However, these metrics are often reported as aggregated or averaged values across a match, obscuring the most demanding passages of play, or worst-case scenario (WCS) demands. WCS demands represent the highest locomotor intensities experienced by players over short, rolling time windows and better reflect peak match demands than whole-match or segment averages. Because injury risk, fatigue, and technical performance breakdowns are likely to occur during these peak periods, preparing players for WCS demands is an important part of effective training design. Despite growing interest in WCS metrics in sport science and periodization plans, these demands are rarely contextualized within the game, limiting their value to the technical staff. Specifically, it remains unclear which in-game events precede WCS demands and how WCS movement sequences can be translated into sport-specific conditioning activities. Therefore, the purpose of this study was to contextualize WCS running demands by identifying preceding in-game events and reconstructing associated player movement sequences to inform tactical teaching and physical preparation.  

### Methods  
Optical tracking data from a single professional soccer match were analyzed for a proof-of-concept. WCS running demands were calculated using a rolling moving-average approach across 30-second, 1-minute, and 2-minute windows. For each player, WCS windows were extracted and temporally aligned with event data using timestamps and frame counts. Events occurring prior to each WCS window were encoded as contextual features. A transparent, interpretable classification model was applied to estimate the contribution of preceding in-game events to the likelihood of entering a WCS window, with explainable AI techniques used to quantify event-level importance. Player trajectories and speed profiles during WCS windows were then reconstructed to characterize individual movement sequences.  

### Results
A generalizable Jupyter Notebook was developed to calculate WCS demands from tracking data, merge them with preceding in-game events on a player-specific basis, and visualize movement sequences during WCS periods for a selected player, allowing the workflow to be applied across matches. 
For the proof-of-concept analyzed match, peak running intensity increased as window duration shortened, with the highest demands observed during 30-second and 1-minute windows, consistent with previous literature (REF). Common preceding events differed across players and positions, with WCS demands emerging from contexts including defensive recovery runs, pressing actions, and attacking transitions. Movement sequence analysis revealed substantial inter-individual variability in how peak demands were accumulated despite similar running intensities.  

### Conclusion
WCS running demands cannot be fully understood through aggregated match metrics alone and should be calculated using tracking data in athlete monitoring paradigms. Identifying the in-game events that precede WCS demands also provides a framework for determining whether exposure to these extremes is necessary or potentially modifiable through teaching. When aligned with the team’s game model, reconstructed WCS movement sequences and technical actions offer a data-supported basis for designing individualized, position-specific conditioning activities. Overall, contextualizing WCS demands represents a critical step in bridging sport science and physical preparation with technical and tactical analysis to provide integrated athlete support.

## How to Run the Code  

1. Prerequisites  
2. Install Pipenv  
3. Set up the environment  
4. Open the notebook  
   Launch `submission_VatneEmaly.ipynb` and choose the Python kernel created by Pipenv.  
5. Run the notebook  
   Select the match(es) that you wish to analyze and the player and window duration for presenting the movement sequences for that WCS demand period.
