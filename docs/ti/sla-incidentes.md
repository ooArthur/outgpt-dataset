---
titulo: "SLA de incidentes e requisições de TI"
area: ti
versao: "2026.1"
vigencia: "2026-01-01"
acesso: publico
responsavel: "TI (ti@brisalog.example)"
status: vigente
---

# SLA de incidentes e requisições de TI

O SLA (acordo de nível de serviço) define em quanto tempo a TI se compromete a **resolver** cada chamado. A prioridade é definida pelo impacto no negócio, não pela urgência de quem abre o chamado.

## Prazos por prioridade

| Prioridade | Prazo de resolução | Primeira resposta | Quando se aplica |
|---|---|---|---|
| P1 | 4 horas | 15 minutos | parada total de um sistema crítico ou de uma unidade (por exemplo, BrisaWMS fora do ar no CD, rede indisponível, suspeita de ataque em andamento) |
| P2 | 8 horas | 1 hora | impacto grave em uma área ou usuário bloqueado sem alternativa (por exemplo, impossibilidade de faturar, VPN fora para o time comercial) |
| P3 | 3 dias úteis | 4 horas | falha com alternativa de contorno ou que afeta uma pessoa (por exemplo, lentidão, impressora, erro em relatório) |
| P4 | 5 dias úteis | 1 dia útil | requisição simples, dúvida ou melhoria (por exemplo, nova licença, instalação de software homologado) |

Os prazos de P3 e P4 são contados em dias úteis. Os de P1 e P2 são contados em horas corridas dentro do horário de atendimento, exceto P1, que tem plantão 24 horas por dia, 7 dias por semana.

## Horário de atendimento

O atendimento regular funciona de segunda a sexta, das 7h às 19h. Para chamados P1 fora desse horário, ligue para o ramal 4000, que é encaminhado ao plantão.

## Como abrir um chamado

1. Acesse o ServiceDesk Brisa pelo Portal Brisa e escolha *Incidente* (algo parou de funcionar) ou *Requisição* (você precisa de algo novo).
2. Descreva o que aconteceu, desde quando e qual o impacto. Anexe uma imagem do erro, se houver.
3. Indique se mais pessoas ou a operação do CD foram afetadas. Isso ajuda a definir a prioridade correta.

Também é possível abrir chamados por e-mail (ti@brisalog.example) ou pelo ramal 4000.

## Filas de atendimento

Os chamados são encaminhados para uma das filas: N1, N2, Infraestrutura, Sistemas, Segurança. O N1 resolve o que é rotineiro, como senhas e dúvidas; as demais filas tratam infraestrutura, sistemas e segurança.

## Exemplos de classificação

- *"O BrisaWMS não abre em nenhum coletor do CD Campinas."* → **P1**, pois a operação está parada.
- *"Não consigo emitir notas fiscais no BrisaERP desde cedo."* → **P2**, porque o faturamento está bloqueado.
- *"Minha impressora está falhando na etiqueta."* → **P3**, pois existe outra impressora no andar.
- *"Preciso do pacote de design instalado."* → **P4**, uma requisição simples.

## O que acontece se o prazo estourar

Quando um chamado chega a 80% do prazo sem solução, o sistema avisa o gerente de Infraestrutura e Suporte. Se o prazo vencer, o solicitante recebe uma atualização com o motivo e a nova previsão. Chamados P1 geram um relato de causa raiz em até 5 dias úteis.

## Reclassificação

Se você acredita que a prioridade está errada, responda ao chamado explicando o impacto. A TI reavalia e pode subir ou baixar a prioridade.

Documento fictício, criado para fins acadêmicos.
