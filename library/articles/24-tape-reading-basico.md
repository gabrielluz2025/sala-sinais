# Tape reading — leitura de fluxo básica

**Tape reading** observa sequência de negócios (times & trades) para inferir agressão compradora ou vendedora.

## Conceitos

- **Agressor comprador**: negócio no ask ou acima.
- **Agressor vendedor**: no bid ou abaixo.
- **Absorção**: muito volume sem deslocar preço.

## B3 day trade

Plataformas mostram lotes e horários. Foque em **papéis líquidos** (PETR4, ITUB4, BBDC4) onde o tape reflete fluxo real.

## Limitações

Tape parcial vs book completo; spoofing e ordens iceberg distorcem leitura. Use tape como **filtro**, não gatilho único.

## Combinação

Candle de rejeição + absorção no nível = setup mais forte. Engine matemático não substitui olho no fluxo — complementa.

## Disciplina

Evitar overtrade ao “ver cada lote”. Defina gatilho objetivo antes de abrir o DOM.
