# Validation report

**34/34 checks passed**

## A. Integridade

| | Check | Detail |
|---|---|---|
| ✅ | Grão único dia x canal x SKU | 24,480 linhas, 24,480 chaves distintas, esperado 24,480 |
| ✅ | De-para de anúncios sem ID externo repetido | 0 IDs externos apontando para mais de um SKU |
| ✅ | Uma linha de ads por dia x canal x SKU | 0 chaves repetidas em stg_ads |
| ✅ | Todo anúncio mapeado para um SKU | 0 linhas de ads sem SKU |
| ✅ | OMS integral no fato (receita bruta) | CSV R$ 20,010,511.22 = fato |
| ✅ | Shopee: duplicatas do re-download removidas | 5,340 linhas brutas -> 5,220 (120 duplicadas em 3 dias sobrepostos) |
| ✅ | Shopee: duplicatas eram cópias idênticas | nenhuma divergência de valores entre as cópias |
| ✅ | Mercado Ads: parsing de vírgula decimal e data BR | pandas R$ 366,991.96 | SQL R$ 366,991.96 |
| ✅ | Mercado Ads: SKUs com 2 anúncios MLB consolidados | 3 SKUs com mais de um MLB |
| ✅ | Amazon: dias sem export viram 'sem medida' | dias sem medida: 2026-07-03, 2026-07-04 |
| ✅ | 'Sem medida' nunca vira zero | 0 linhas sem medida com valor preenchido |
| ✅ | Grupo apagado sem gasto nem atribuição no teste | soma = 0.0 |
| ✅ | Grupo ligado com gasto em todo dia medido | 0 dias medidos sem gasto |
| ✅ | Balanceamento dos grupos no pré-teste (±10%) | Amazon: 0,958 | Mercado Livre: 0,965 | Shopee: 1,002 | TikTok Shop: 1,008 |

## B. Lógica e casos-teste

| | Check | Detail |
|---|---|---|
| ✅ | TikTok: coluna roi = receita bruta / custo | maior desvio 0.0000 |
| ✅ | ROI protection recalculado bate com o extrato | 156 dias-campanha com crédito no SQL, 156 no extrato, maior diferença R$ 0.00 |
| ✅ | Crédito nunca maior que o custo do dia | 0 violações |
| ✅ | Rateio de créditos por SKU fecha com o total | diferença R$ 0.0000 |
| ✅ | Cascata fecha: soma dos degraus = lucro incremental | Amazon: R$ 27.975 | Mercado Livre: R$ -69.680 | TikTok Shop: R$ -72.616 | Shopee: R$ -17.085 |
| ✅ | Identidade do break-even: ROAS x k x cm = 1 | maior desvio 2.22e-16 |
| ✅ | Custos + margem somam 100% da receita | maior desvio 2.44e-15 |
| ✅ | Investimento total = soma dos 4 exports (independente) | marts R$ 1,139,552.63 | CSVs R$ 1,139,552.63 |
| ✅ | Caso-teste: Break-even: cm 25%, k 0,40 | calculado 10.00, esperado à mão 10.00 |
| ✅ | Caso-teste: Crédito ROI protection: custo 1.000, receita 4.000, meta 5,0 | calculado 111.11, esperado à mão 111.11 |
| ✅ | Caso-teste: ACOS máximo: cm 30%, k 0,50 | calculado 0.15, esperado à mão 0.15 |
| ✅ | Caso-teste: estimador DiD em exemplo de 2 SKUs | calculado 1.50, esperado 1,50 |

## C. Recuperação da verdade plantada

| | Check | Detail |
|---|---|---|
| ✅ | Amazon: iROAS verdadeiro dentro do IC 95% | verdade 3,68 | estimado 3,74 [2,74; 4,74] |
| ✅ | Amazon: k verdadeiro dentro do IC 95% | verdade 0,687 | estimado 0,688 [0,526; 0,850] |
| ✅ | Mercado Livre: iROAS verdadeiro dentro do IC 95% | verdade 3,17 | estimado 3,31 [2,47; 4,16] |
| ✅ | Mercado Livre: k verdadeiro dentro do IC 95% | verdade 0,546 | estimado 0,571 [0,435; 0,708] |
| ✅ | Shopee: iROAS verdadeiro dentro do IC 95% | verdade 2,48 | estimado 2,94 [2,24; 3,64] |
| ✅ | Shopee: k verdadeiro dentro do IC 95% | verdade 0,515 | estimado 0,604 [0,485; 0,723] |
| ✅ | TikTok Shop: iROAS verdadeiro dentro do IC 95% | verdade 1,99 | estimado 2,25 [1,52; 2,98] |
| ✅ | TikTok Shop: k verdadeiro dentro do IC 95% | verdade 0,377 | estimado 0,410 [0,297; 0,522] |
