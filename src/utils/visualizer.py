from typing import List
import plotly.graph_objects as go
from src.models.matching_schemas import DimensionScore


def generate_radar_chart(radar_data: List[DimensionScore]) -> go.Figure:
    """
    Generates a dual-polygon radar chart comparing Job Requirements vs. Candidate Capability.

    Args:
        radar_data: List of DimensionScore items.

    Returns:
        Plotly Figure object ready for UI rendering.
    """
    dimensions = [item.dimension for item in radar_data]
    job_scores = [item.job_requirement for item in radar_data]
    candidate_scores = [item.candidate_capability for item in radar_data]

    # Close polar loop by appending the first item at the end
    dimensions.append(dimensions[0])
    job_scores.append(job_scores[0])
    candidate_scores.append(candidate_scores[0])

    fig = go.Figure()

    # Job target layer
    fig.add_trace(
        go.Scatterpolar(
            r=job_scores,
            theta=dimensions,
            fill="toself",
            name="Job Requirement (Benchmark)",
            line=dict(color="#FF6384", width=2),
            fillcolor="rgba(255, 99, 132, 0.2)",
        )
    )

    # Candidate assessed layer
    fig.add_trace(
        go.Scatterpolar(
            r=candidate_scores,
            theta=dimensions,
            fill="toself",
            name="Candidate Assessment",
            line=dict(color="#36A2EB", width=2),
            fillcolor="rgba(54, 162, 235, 0.3)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10),
            )
        ),
        showlegend=True,
        title=dict(
            text="Competency Benchmark vs. Candidate Capability",
            x=0.5,
            xanchor="center",
        ),
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig