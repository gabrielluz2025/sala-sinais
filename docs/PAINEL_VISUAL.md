# Painel web — Aurora v3

## O que mudou (reimaginação completa)

- **Design system dedicado:** tokens em `web/design-system.css` (tipografia Plus Jakarta Sans, números JetBrains Mono, paleta violeta/ciano, claro/escuro automático ou manual).
- **Shell e componentes:** `web/app-shell.css` — layout com rail lateral no desktop, **dock flutuante** no mobile, cards `rounded-2xl`, mesh de fundo, animações leves (entrada de zonas, pulse do engine ao vivo, skeleton nos gráficos, flash nos KPIs).
- **Home do dashboard:** bloco hero **Resultado de hoje** + faixa de sessão (modo, ativo, estratégia) no topo.
- **Temas:** **Aurora v3** (padrão) | **Visual antigo** (`legacy.css`, ex-tema Clássico). Botões **Auto / Claro / Escuro** para `data-color-mode` no `<html>`.
- **Removidos:** `theme-pro.css`, `theme-classic.css` (substituídos por `legacy.css`).

## Funcionalidade preservada

- Mesmos endpoints e lógica em `web/app.js` (fetch, zonas, config do agente, biblioteca export/import, gráficos Chart.js).
- IDs exigidos pelos testes em `tests/test_web_dashboard_ids.py`.

## Como ver a mudança

1. **Ctrl+F5** no navegador (cache bust `?v=3` nos CSS/JS).
2. Confirme **Aurora v3** no topo; use **Visual antigo** só se quiser o layout cyan/glass anterior.
3. No mobile, use o dock inferior; no desktop, o menu lateral com alvos grandes.

## Arquivos principais

| Arquivo | Função |
|---------|--------|
| `web/design-system.css` | Tokens, tipografia, utilitários, animações base |
| `web/app-shell.css` | Layout, sidebar, dock, cards, tabelas, zonas |
| `web/legacy.css` | Visual antigo (link desabilitado até escolher “Visual antigo”) |
| `web/style.css` | `@import` de design-system + app-shell (compatibilidade) |
| `web/index.html` | Entrada única do painel |
| `web/app.js` | Dados, tema Aurora/legacy, modo claro/escuro |
