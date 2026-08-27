# Análisis bayesiano y recomendación de financiación

## Supuestos
- Tamaño de efecto Hedges' *g* observado ~ Normal(δ, SE²).
- Priori para el efecto verdadero: δ ~ N(μ=0.0, σ=0.5).
- Umbral mínimo educativamente relevante: g = 0.1.
- Regla de decisión: financiar si P(δ > 0.1) > 80%.

## Resultados posteriores
- Finding 1 (high-ability): δ ~ N(0.322, 0.077²), P(δ > 0) = 99.999%, P(δ > 0.1) = 99.803%.
- Finding 2 (regular): δ ~ N(-0.463, 0.094²), P(δ > 0) = 0.000%, P(δ > 0.1) = 0.000%.
- Población general (supuesta mezcla): δ ~ N(-0.070, 0.061²), P(δ > 0) = 12.383%, P(δ > 0.1) = 0.257%.

## Recomendación
Financiar **solo si la iniciativa se dirige a estudiantes de alta habilidad**. El posterior indica un efecto positivo y relevante con alta probabilidad.
No se recomienda financiar para estudiantes regulares ni para toda la población escolar, ya que el efecto esperado para la población mezclada es negativo o cercano a cero.

## Circunstancias para financiar
- La iniciativa puede **segmentar y atender exclusivamente a estudiantes de alta habilidad**.
- El costo por estudiante es menor que el valor monetario esperado del beneficio (valor de 0.32 unidades de Hedges' g por participante).
- Se acepta el supuesto de que los efectos observados en 1986 son transportables al contexto actual.
- Se monitorea el impacto en los estudiantes regulares para evitar externalidades negativas.