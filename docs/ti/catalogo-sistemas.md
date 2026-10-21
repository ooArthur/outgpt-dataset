---
titulo: "Catálogo de sistemas internos"
area: ti
versao: "2026.1"
vigencia: "2026-01-01"
acesso: publico
responsavel: "TI (ti@brisalog.example)"
status: vigente
---

# Catálogo de sistemas internos

Este catálogo reúne os sistemas usados na Brisa Log, para que você saiba para que serve cada um, quem é o dono do processo e a qual fila da TI recorrer em caso de problema.

## Visão geral

| Sistema | Para que serve | Dono do processo | Fila de suporte |
|---|---|---|---|
| BrisaERP | finanças, compras, faturamento e despesas | Financeiro e Controladoria | Sistemas |
| BrisaWMS | gestão de armazém: recebimento, estoque, separação e expedição | Operações e Logística | Sistemas |
| RotaViva | gestão de transporte, roteirização e monitoramento de entregas | Operações e Logística | Sistemas |
| PessoasHub | férias, holerites, benefícios e dados cadastrais | Pessoas e Cultura | Sistemas |
| PontoBrisa | registro e ajuste de ponto | Pessoas e Cultura | N1 |
| BrisaDocs | gestão documental e pastas compartilhadas | TI | N2 |
| Portal Brisa | intranet com políticas, comunicados e diretório | Pessoas e Cultura | N1 |
| ServiceDesk Brisa | abertura e acompanhamento de chamados de TI | TI | N1 |
| BrisaVPN | acesso remoto seguro à rede interna | TI | Infraestrutura |
| BrisaCofre | gerenciador de senhas corporativo | TI | Segurança |
| BrisaMail | e-mail e agenda corporativos | TI | N1 |
| BrisaChat | mensagens e reuniões por vídeo | TI | N1 |

O **dono do processo** decide regras de negócio e aprova acessos. A **fila de suporte** é o time de TI que resolve falhas técnicas.

## Como pedir acesso

O gestor abre uma requisição no ServiceDesk Brisa informando o sistema e o perfil desejado. O dono do processo aprova, e a TI concede. Prazo típico: P4, ou seja, até 5 dias úteis. Veja o documento de acesso e senhas.

## Qual sistema devo usar para...

- **Registrar uma entrada de mercadoria:** BrisaWMS.
- **Programar uma rota de entrega:** RotaViva.
- **Pedir reembolso ou comprar:** BrisaERP.
- **Pedir férias ou ver holerite:** PessoasHub.
- **Ajustar ponto:** PontoBrisa.
- **Abrir chamado de TI:** ServiceDesk Brisa.
- **Buscar políticas e ramais:** Portal Brisa.

## Ciclo de manutenção

Atualizações programadas dos sistemas são avisadas com antecedência no Brisa em Foco e no BrisaChat. Mudanças de alto impacto, como atualizações do BrisaWMS, são feitas fora do horário de pico dos CDs.

## Disponibilidade

Falhas que paralisam um CD são tratadas como P1: resolução em até 4 horas. Para o caso de falhas com contorno, aplicam-se os prazos de P2 ou P3 descritos no SLA de incidentes.

## Integrações

O BrisaERP recebe os dados de faturamento do BrisaWMS e do RotaViva. Por isso, divergências em estoque ou frete afetam o fechamento contábil e devem ser corrigidas antes do corte.

## Dúvidas

Para sugerir melhorias em sistemas, escreva para ti@brisalog.example.

Documento fictício, criado para fins acadêmicos.
