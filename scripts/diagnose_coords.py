"""Check coordinate coverage per state for A+B tier settlements."""
from grid_intelligence.db import read_df

df = read_df("""
    SELECT
        state,
        COUNT(*) FILTER (WHERE viability_tier IN ('A_highly_viable', 'B_viable')) AS ab_settlements,
        COUNT(*) FILTER (
            WHERE viability_tier IN ('A_highly_viable', 'B_viable')
              AND latitude IS NOT NULL AND longitude IS NOT NULL
        ) AS ab_with_coords,
        ROUND(AVG(latitude)::numeric, 3) AS avg_lat,
        ROUND(AVG(longitude)::numeric, 3) AS avg_lon
    FROM dbt_dev_marts.fct_minigrid_viability
    GROUP BY 1
    ORDER BY 3 DESC
""")
print(df.to_string(index=False))
