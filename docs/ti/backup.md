---
titulo: "Política de backup e recuperação"
area: ti
versao: "2026.1"
vigencia: "2026-01-01"
acesso: publico
responsavel: "TI (ti@brisalog.example)"
status: vigente
---

# Política de backup e recuperação

Backup é a cópia de segurança que permite recuperar informações depois de um erro, falha ou incidente. Esta política descreve o que é copiado, com que frequência, por quanto tempo e como pedir uma restauração.

## O que é copiado

- Servidores e bancos de dados do BrisaERP, do BrisaWMS, do RotaViva e do PessoasHub.
- Pastas compartilhadas no BrisaDocs.
- Caixas de e-mail no BrisaMail.

**Não são copiados** automaticamente os arquivos salvos apenas no disco do notebook, na área de trabalho ou em nuvens pessoais. Guarde os arquivos de trabalho no BrisaDocs.

## Frequência

| Tipo | Frequência |
|---|---|
| Incremental | diário, às 22h |
| Completo | semanal, aos domingos |
| Teste de restauração | trimestral |

## Retenção

- Cópias diárias são mantidas por **30 dias**.
- Cópias mensais são mantidas por **12 meses**.

Depois desses prazos, as cópias são eliminadas, respeitando as regras da LGPD e de guarda de documentos fiscais.

## Metas de recuperação

- **RPO (quanto dado podemos perder): 24 horas.** Em um incidente grave, perde-se, no máximo, o trabalho do último dia.
- **RTO (em quanto tempo restauramos os serviços críticos): 8 horas.**

## Como pedir a restauração de um arquivo

1. Abra um chamado no ServiceDesk Brisa em *Restauração de arquivo*.
2. Informe o caminho da pasta, o nome do arquivo e a data aproximada em que ele existia.
3. A TI localiza a versão e a devolve em uma pasta temporária. Em geral, esse chamado é P3.

Se o arquivo foi apagado há mais tempo que o prazo de retenção, a recuperação pode não ser possível.

## Boas práticas

- Salve no BrisaDocs desde o início do trabalho.
- Evite nomes como "final_v2_agora_vai".
- Nunca guarde senhas em planilhas; use o BrisaCofre.

## Testes e auditoria

O teste de restauração, de frequência trimestral, escolhe sistemas diferentes a cada vez e o resultado é registrado e revisado pelo gerente de Infraestrutura e Suporte.

## Dúvidas

ti@brisalog.example.

Documento fictício, criado para fins acadêmicos.
