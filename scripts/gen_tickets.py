"""Gera tickets/tickets_ti.csv (500 tickets sintéticos em PT-BR) coerentes com o SLA da ficha-mestra."""
import datetime as dt
import random

from common import carregar_ficha, escrever_csv, normaliza, sem_acento

N_TICKETS = 500
SISTEMAS = ["BrisaERP", "BrisaWMS", "RotaViva", "PessoasHub", "PontoBrisa", "BrisaDocs", "Portal Brisa", "BrisaChat"]
SISTEMAS_ACESSO = ["BrisaERP", "BrisaWMS", "RotaViva", "PessoasHub", "BrisaDocs"]
LOCAIS = ["sala de reuniões do 2º andar", "recepção", "sala de expedição", "área da doca 7", "área de separação", "sala do Financeiro",
          "copa do 1º andar", "sala do Comercial", "sala do mezanino", "sala de atendimento de Uberlândia", "sala de treinamento", "portaria do CD"]
SOFTWARES = ["Excel", "Word", "PowerPoint", "Adobe Reader", "o leitor de PDF", "o navegador", "o editor de planilhas", "o programa de videoconferência", "o Power BI"]
EQUIPS = ["notebook", "monitor", "mouse", "teclado", "headset", "webcam", "carregador", "dock station"]
MOTIVOS_PICO = ["fechamento do mês", "o pico de entregas", "a auditoria de quarta", "a visita do cliente", "o inventário do CD"]

# (categoria, fila, tipo, [(prioridade, peso)], assuntos, descrições, departamentos preferenciais ou None)
CENARIOS = [
    # ----- Acesso e Senhas
    ("Acesso e Senhas", "N1", "incidente", [("P3", 1)],
     ["Conta bloqueada", "Não consigo entrar na minha conta", "Usuário bloqueado após tentativas"],
     ["Errei a senha algumas vezes e minha conta ficou bloqueada. Preciso desbloquear para acessar o {s}.",
      "Minha conta foi bloqueada hoje cedo e não consigo entrar no {s} nem no e-mail.",
      "O sistema diz que minha conta está bloqueada por excesso de tentativas. Podem liberar?"], None),
    ("Acesso e Senhas", "N1", "incidente", [("P3", 1)],
     ["Esqueci a senha do {s}", "Redefinição de senha do {s}", "Senha do {s} não funciona"],
     ["Esqueci minha senha do {s} e o autoatendimento não funcionou. Preciso de uma nova senha.",
      "Tentei redefinir a senha do {s} pelo link, mas o código não chega. Podem ajudar?",
      "A senha do {s} expirou e o sistema não aceita a nova que eu cadastrei."], None),
    ("Acesso e Senhas", "N1", "requisição", [("P3", 1)],
     ["Trocar celular do MFA", "Autenticador no celular novo", "Migrar verificação em duas etapas"],
     ["Troquei de celular e perdi o aplicativo autenticador. Preciso cadastrar o MFA no aparelho novo.",
      "Meu celular foi formatado e o MFA parou de funcionar. Como faço para reconfigurar?",
      "Ganhei um celular novo e ainda não consegui passar o autenticador. Preciso de ajuda para migrar."], None),
    ("Acesso e Senhas", "N1", "incidente", [("P2", 1)],
     ["MFA não gera código", "Código do autenticador inválido", "Não consigo passar na verificação em duas etapas"],
     ["O código do autenticador aparece como inválido e estou bloqueado de tudo, inclusive do {s}, e tenho {m} hoje.",
      "O aplicativo autenticador está mostrando códigos que o sistema recusa. Não consigo acessar nada e preciso trabalhar por causa do {m}.",
      "Verificação em duas etapas falhando desde cedo. Estou sem acesso ao e-mail e ao {s}."], None),
    ("Acesso e Senhas", "Sistemas", "requisição", [("P4", 1)],
     ["Solicitação de acesso ao {s}", "Liberar acesso ao {s} para novo perfil", "Acesso ao {s}"],
     ["Preciso de acesso ao {s} com perfil de consulta. O gestor já está ciente.",
      "Por favor, liberar acesso ao {s} para eu atuar na nova função. Aprovação do gestor em anexo.",
      "Solicito acesso ao {s}, perfil de operação, a partir da próxima semana."], None),
    ("Acesso e Senhas", "N1", "requisição", [("P4", 1)],
     ["Acesso a pasta compartilhada", "Permissão na pasta do BrisaDocs", "Liberar pasta da equipe"],
     ["Preciso de acesso de leitura à pasta da equipe no BrisaDocs para consultar os contratos.",
      "Podem liberar minha permissão de edição na pasta de relatórios mensais do BrisaDocs?",
      "Mudei de área e preciso acessar a pasta da nova equipe no BrisaDocs."], None),
    ("Acesso e Senhas", "N1", "requisição", [("P4", 1)],
     ["Criar contas para novo colaborador", "Novo colaborador começa segunda", "Contas para admissão"],
     ["Temos um colaborador novo começando na segunda. Precisamos de e-mail, BrisaChat e PessoasHub.",
      "Admissão confirmada para a próxima semana. Favor criar usuário, e-mail e acessos básicos.",
      "Preciso das contas de um novo integrante da equipe, que inicia dia primeiro."], ["Pessoas e Cultura", "Operações e Logística", "Comercial"]),
    ("Acesso e Senhas", "Segurança", "requisição", [("P3", 1)],
     ["Desligamento: remover acessos", "Encerrar acessos de ex-colaborador", "Bloqueio de contas por desligamento"],
     ["Colaborador desligado hoje. Favor encerrar todos os acessos e recolher o equipamento.",
      "Precisamos bloquear imediatamente as contas de um desligamento ocorrido agora há pouco.",
      "Desligamento de um motorista: remover acessos ao RotaViva e ao e-mail."], ["Pessoas e Cultura", "Operações e Logística"]),
    ("Acesso e Senhas", "Sistemas", "incidente", [("P2", 1)],
     ["Turno sem acesso ao BrisaWMS", "Operadores sem login no WMS", "Equipe do CD não consegue logar no WMS"],
     ["Os operadores do turno não conseguem logar no BrisaWMS nos coletores. A separação está parada para {n} pessoas.",
      "Login do WMS recusando usuários do turno inteiro no CD. Sem acesso, não temos como separar pedidos.",
      "Desde o início do turno ninguém entra no BrisaWMS pelos coletores. Preciso de ajuda para o pessoal voltar a trabalhar."], ["Operações e Logística"]),
    # ----- E-mail e Colaboração
    ("E-mail e Colaboração", "N1", "incidente", [("P3", 1)],
     ["Caixa de e-mail cheia", "Mailbox lotada", "Não consigo receber e-mails por falta de espaço"],
     ["Minha caixa de e-mail está cheia e parei de receber mensagens. Preciso de mais espaço ou de ajuda para limpar.",
      "Recebi o aviso de que a caixa de entrada atingiu o limite. Podem liberar espaço?",
      "O BrisaMail diz que estou sem espaço e não consigo enviar nem receber."], None),
    ("E-mail e Colaboração", "N2", "incidente", [("P3", 0.7), ("P2", 0.3)],
     ["Não recebo e-mails de clientes", "E-mails de um domínio não chegam", "Mensagens externas sumindo"],
     ["Há dois dias não recebo e-mails de um cliente específico. Já pedi para ele reenviar e nada chegou.",
      "Os e-mails do domínio de um fornecedor não chegam na minha caixa, nem no spam. Precisamos confirmar uma proposta.",
      "Mensagens de clientes externos estão sumindo. Pode ser algum bloqueio?"], ["Comercial", "Financeiro e Controladoria", "Operações e Logística"]),
    ("E-mail e Colaboração", "Infraestrutura", "incidente", [("P1", 1)],
     ["BrisaMail fora do ar", "E-mail indisponível para todos", "Ninguém consegue acessar o e-mail"],
     ["O BrisaMail está fora do ar para todo mundo aqui. Não conseguimos enviar nem receber, e estamos no {m}.",
      "E-mail corporativo fora desde as primeiras horas da manhã, em Campinas e Uberlândia. Isso está parando as comunicações.",
      "Ninguém da empresa consegue acessar o e-mail. Preciso de retorno imediato."], None),
    ("E-mail e Colaboração", "N1", "incidente", [("P3", 1)],
     ["Sem áudio na reunião", "Câmera não funciona no BrisaChat", "Problema de vídeo nas reuniões"],
     ["Nas reuniões pelo BrisaChat ninguém me ouve, mas eu ouço todo mundo. Já testei outro fone.",
      "A câmera não abre no BrisaChat e tenho uma apresentação com cliente amanhã.",
      "O compartilhamento de tela não funciona nas chamadas. Aparece só uma tela preta."], None),
    ("E-mail e Colaboração", "N1", "requisição", [("P4", 1)],
     ["Criar lista de distribuição", "Novo grupo de e-mail", "Grupo de e-mail para a equipe"],
     ["Preciso de um grupo de e-mail para a equipe de {d}, com todos os integrantes.",
      "Podem criar uma lista de distribuição para a nova célula de trabalho? Sigo com a lista de nomes.",
      "Solicito a criação de uma caixa compartilhada para o time responder clientes."], None),
    ("E-mail e Colaboração", "N1", "requisição", [("P4", 1)],
     ["Assinatura de e-mail padrão", "Atualizar assinatura do e-mail", "Agenda compartilhada"],
     ["Mudei de cargo e preciso atualizar a assinatura padrão do meu e-mail.",
      "Gostaria de compartilhar minha agenda com a assistente. Podem configurar?",
      "Preciso do modelo atualizado da assinatura de e-mail com o novo layout."], None),
    # ----- Rede e VPN
    ("Rede e VPN", "N2", "incidente", [("P3", 0.75), ("P2", 0.25)],
     ["BrisaVPN não conecta", "VPN dando erro", "Sem acesso remoto"],
     ["A BrisaVPN não conecta de casa. Aparece erro de autenticação logo depois do código do MFA.",
      "Estou em home office e a VPN cai a cada poucos minutos, não consigo acessar o BrisaERP.",
      "Instalei a atualização e a VPN deixou de funcionar. Já reiniciei o notebook."], ["Comercial", "Financeiro e Controladoria", "TI", "Pessoas e Cultura"]),
    ("Rede e VPN", "Infraestrutura", "incidente", [("P3", 1)],
     ["Wi-Fi instável na {l}", "Wi-Fi caindo", "Internet sem sinal na {l}"],
     ["O Wi-Fi da {l} cai toda hora. Em videochamadas, a conexão é perdida.",
      "Sem sinal de Wi-Fi na {l} desde ontem. Por cabo funciona normalmente.",
      "A rede sem fio está muito instável na {l}. Alguns colegas também reclamam."], None),
    ("Rede e VPN", "Infraestrutura", "incidente", [("P1", 1)],
     ["CD sem rede", "Rede fora do ar no CD", "Link da unidade caiu"],
     ["O CD está totalmente sem rede. Coletores sem comunicação com o BrisaWMS e a expedição está parada.",
      "A rede da unidade caiu e ninguém acessa sistema algum. Operação inteira parada.",
      "Link de internet do CD fora do ar. Não conseguimos emitir documentos de transporte e os caminhões estão parados."], ["Operações e Logística"]),
    ("Rede e VPN", "Infraestrutura", "incidente", [("P3", 1)],
     ["Internet lenta", "Lentidão na rede", "Navegação muito lenta"],
     ["A internet está muito lenta no meu setor desde a manhã. Páginas do sistema demoram para abrir.",
      "Lentidão geral na rede da minha área. Downloads param e as chamadas ficam travando.",
      "Está demorando muito para abrir qualquer página. Só acontece aqui na sala."], None),
    ("Rede e VPN", "N2", "requisição", [("P4", 1)],
     ["Liberar site bloqueado", "Acesso a site para trabalho", "Site bloqueado pelo filtro"],
     ["O filtro está bloqueando o site de um fornecedor que preciso consultar para cotação. Podem liberar?",
      "Preciso acessar o portal da transportadora, mas aparece como bloqueado.",
      "Solicito liberação de um site de consulta de legislação, que é necessário para o meu trabalho."], None),
    ("Rede e VPN", "Infraestrutura", "requisição", [("P4", 1)],
     ["Ponto de rede novo", "Ponto de rede na {l}", "Instalar ponto de rede"],
     ["Precisamos de um ponto de rede adicional na {l} para um novo posto de trabalho.",
      "Vamos remanejar a equipe e preciso de dois pontos de rede novos na {l}.",
      "Solicito instalação de um ponto de rede para uma impressora na {l}."], None),
    # ----- Hardware
    ("Hardware", "N1", "incidente", [("P2", 0.6), ("P3", 0.4)],
     ["Notebook não liga", "Notebook não inicia", "Notebook parou de ligar"],
     ["Meu notebook não liga de jeito nenhum. A luz acende, mas a tela fica preta. Preciso trabalhar por causa do {m}.",
      "O notebook desligou do nada e agora não inicia mais. Tem arquivos importantes no equipamento.",
      "Notebook morreu hoje de manhã. Já tentei outro carregador."], None),
    ("Hardware", "N1", "incidente", [("P3", 1)],
     ["Notebook muito lento", "Computador travando", "Lentidão no equipamento"],
     ["Meu notebook está extremamente lento, demora minutos para abrir {sw}.",
      "O computador trava toda hora e às vezes reinicia sozinho.",
      "Desde a última atualização o equipamento ficou lento e a ventoinha faz muito barulho."], None),
    ("Hardware", "N1", "incidente", [("P3", 1)],
     ["Monitor sem imagem", "Monitor com tela piscando", "Problema no monitor"],
     ["O monitor da minha mesa não dá imagem. Já troquei o cabo e nada.",
      "A tela do monitor fica piscando e dá dor de cabeça.",
      "Monitor apresentando listras na tela. Preciso de um novo ou de reparo."], None),
    ("Hardware", "N1", "incidente", [("P4", 0.5), ("P3", 0.5)],
     ["Teclado com teclas falhando", "Mouse parou de funcionar", "Defeito no periférico"],
     ["Algumas teclas do teclado não funcionam. Atrapalha na digitação de pedidos.",
      "O mouse não responde mais, mesmo trocando a pilha.",
      "O headset ficou com um chiado alto e o microfone não funciona."], None),
    ("Hardware", "N1", "incidente", [("P2", 0.5), ("P3", 0.5)],
     ["Coletor de dados quebrado", "Coletor do CD não liga", "Coletor com tela trincada"],
     ["O coletor de dados {n} da separação caiu e a tela trincou. Está sem comunicação com o BrisaWMS.",
      "Um dos coletores do turno não liga mais. Estamos com menos equipamentos do que pessoas para separar.",
      "Coletor de dados com o gatilho quebrado, não lê código de barras."], ["Operações e Logística"]),
    ("Hardware", "N1", "requisição", [("P4", 1)],
     ["Solicito monitor adicional", "Pedido de {e}", "Equipamento para home office"],
     ["Estou em home office dois dias por semana e gostaria de solicitar um monitor adicional. Gestor de acordo.",
      "Preciso de um {e} novo para a minha estação de trabalho. O atual está desgastado.",
      "Solicito um headset com microfone para as reuniões com clientes."], None),
    ("Hardware", "N1", "incidente", [("P3", 1)],
     ["Bateria do notebook dura pouco", "Notebook desliga fora da tomada", "Carregador não carrega"],
     ["A bateria do notebook dura menos de uma hora. Preciso trabalhar em reuniões fora da mesa.",
      "O notebook só funciona ligado na tomada e desliga quando tiro o carregador.",
      "O carregador esquenta muito e às vezes o notebook não carrega."], None),
    # ----- Software e Licenças
    ("Software e Licenças", "N1", "requisição", [("P4", 1)],
     ["Instalar {sw}", "Instalação de software homologado", "Solicito instalação de {sw}"],
     ["Preciso que instalem {sw} no meu notebook para atividades da minha área.",
      "Favor instalar {sw} no equipamento. Aprovação do gestor em anexo.",
      "Gostaria de instalar o software de desenho técnico homologado pela TI."], None),
    ("Software e Licenças", "N1", "incidente", [("P3", 1)],
     ["Licença do {sw} expirou", "Aviso de licença expirada", "Programa pedindo ativação"],
     ["A licença do {sw} expirou e o programa só abre em modo leitura. Preciso editar os arquivos ainda hoje.",
      "Aparece uma mensagem de produto não ativado no {sw} toda vez que abro.",
      "Meu {sw} pede uma chave de ativação que não tenho."], None),
    ("Software e Licenças", "N1", "incidente", [("P3", 1)],
     ["{sw} travando", "Programa fecha sozinho", "Erro ao abrir arquivo"],
     ["Toda vez que abro um arquivo grande, {sw} congela e fecha sem salvar.",
      "Aparece um erro ao abrir a planilha de pedidos e o programa trava.",
      "{sw} fecha sozinho depois de alguns minutos de uso."], None),
    ("Software e Licenças", "N1", "requisição", [("P4", 1)],
     ["Solicitar nova licença", "Licença para novo usuário", "Compra de licença"],
     ["Preciso de uma licença do {sw} para um novo integrante da equipe.",
      "Solicito licença de uso do {sw} para o ano. Orçamento já aprovado pela diretoria.",
      "Podem informar o procedimento e o custo para uma licença adicional do {sw}?"], None),
    ("Software e Licenças", "N2", "incidente", [("P3", 1)],
     ["Antivírus bloqueou programa", "Atualização quebrou o {sw}", "Aplicativo parou depois da atualização"],
     ["O antivírus bloqueou um programa que uso no trabalho e não consigo executá-lo.",
      "Depois da atualização automática de ontem, {sw} deixou de abrir.",
      "Após uma atualização do Windows meu aplicativo de relatórios não inicia mais."], None),
    # ----- Sistemas Internos
    ("Sistemas Internos", "Sistemas", "incidente", [("P1", 1)],
     ["BrisaWMS fora do ar", "WMS indisponível no CD", "Sistema do armazém caiu"],
     ["O BrisaWMS está fora do ar no CD inteiro. Recebimento, separação e expedição estão parados.",
      "O WMS não responde em nenhum coletor ou computador. Operação 100% parada e os caminhões estão aguardando.",
      "Sistema do armazém indisponível desde o início do turno. Precisamos de ação imediata."], ["Operações e Logística"]),
    ("Sistemas Internos", "Sistemas", "incidente", [("P2", 0.6), ("P3", 0.4)],
     ["BrisaWMS lento no recebimento", "Lentidão no WMS", "Demora ao confirmar separação"],
     ["O BrisaWMS está muito lento na confirmação do recebimento. Cada palete leva minutos e fila de caminhões está aumentando.",
      "Lentidão na tela de separação do BrisaWMS, só acontece em alguns coletores.",
      "O sistema demora para responder no fechamento da onda de picking."], ["Operações e Logística"]),
    ("Sistemas Internos", "Sistemas", "incidente", [("P2", 1)],
     ["Erro ao emitir nota fiscal", "Não consigo faturar no BrisaERP", "Faturamento travado"],
     ["O BrisaERP retorna erro ao emitir nota fiscal desde cedo. O faturamento do dia está bloqueado.",
      "Não consigo emitir NF para nenhum cliente. Aparece uma mensagem de falha de comunicação.",
      "Faturamento parado por erro no emissor de notas do BrisaERP. Estamos no {m}."], ["Financeiro e Controladoria", "Comercial"]),
    ("Sistemas Internos", "Sistemas", "incidente", [("P3", 1)],
     ["Valor divergente em relatório", "Relatório do BrisaERP com erro", "Divergência no relatório de estoque"],
     ["O relatório de contas a pagar do BrisaERP mostra um total diferente do detalhe. Preciso validar antes do fechamento.",
      "O relatório de estoque do BrisaWMS está com saldo diferente do físico. Pode ser problema de sincronização.",
      "Relatório mensal exportando sem as últimas linhas."], ["Financeiro e Controladoria", "Operações e Logística"]),
    ("Sistemas Internos", "Sistemas", "incidente", [("P2", 0.4), ("P3", 0.6)],
     ["RotaViva não atualiza posição", "Rastreamento parado no RotaViva", "Erro ao roteirizar"],
     ["O RotaViva não atualiza a posição dos veículos desde a manhã. Os clientes estão ligando para saber das entregas.",
      "Ao fechar a roteirização, o sistema devolve erro e não gera as rotas do dia.",
      "O monitoramento de temperatura de um veículo não aparece no RotaViva."], ["Operações e Logística"]),
    ("Sistemas Internos", "Sistemas", "incidente", [("P3", 1)],
     ["Erro ao pedir férias no PessoasHub", "PessoasHub com erro", "Holerite não abre"],
     ["Ao solicitar férias no PessoasHub aparece erro e o pedido não é enviado.",
      "O PessoasHub não abre o meu holerite, a página fica carregando.",
      "Não consigo atualizar meus dados cadastrais no PessoasHub."], ["Pessoas e Cultura", "Comercial", "Operações e Logística", "Financeiro e Controladoria"]),
    ("Sistemas Internos", "N1", "incidente", [("P3", 0.7), ("P2", 0.3)],
     ["PontoBrisa não registra", "Erro ao bater o ponto", "Ponto sem sincronizar"],
     ["O PontoBrisa não registra a minha marcação no aplicativo. Aparece erro de sincronização.",
      "O relógio de ponto do CD não reconhece o crachá de vários colegas do turno.",
      "Meu ponto de ontem aparece sem a saída e não consigo ajustar pelo sistema."], ["Operações e Logística", "Pessoas e Cultura"]),
    ("Sistemas Internos", "Sistemas", "requisição", [("P4", 1)],
     ["Novo relatório no BrisaERP", "Ajuste de perfil no sistema", "Melhoria no cadastro"],
     ["Gostaria de solicitar um relatório novo de aging de contas a receber no BrisaERP.",
      "Podem incluir um campo de observação no cadastro de clientes?",
      "Preciso ajustar meu perfil no BrisaWMS para aprovar ajustes de estoque."], ["Financeiro e Controladoria", "Comercial", "Operações e Logística"]),
    # ----- Impressão
    ("Impressão", "N1", "incidente", [("P3", 1)],
     ["Impressora não imprime", "Fila de impressão travada", "Impressora offline"],
     ["A impressora da {l} não imprime. Os documentos ficam na fila e nada sai.",
      "Impressora aparece offline no meu computador, mas está ligada.",
      "Mandei imprimir uma proposta e a fila travou. Já cancelei e tentei de novo."], None),
    ("Impressão", "N1", "incidente", [("P3", 1)],
     ["Papel atolando", "Impressão com manchas", "Impressora com defeito"],
     ["A impressora está atolando papel a todo momento.",
      "As páginas saem com listras pretas. Parece problema no cartucho.",
      "A impressora faz um barulho estranho e não puxa o papel."], None),
    ("Impressão", "N1", "incidente", [("P2", 1)],
     ["Impressora de etiquetas parada", "Etiquetadora térmica do CD não imprime", "Etiquetas saindo em branco"],
     ["A impressora térmica de etiquetas da expedição parou e não conseguimos identificar os volumes. Carga aguardando.",
      "Etiquetas saindo em branco na doca. Sem elas não podemos liberar os caminhões.",
      "A etiquetadora travou no meio do carregamento e a fila de expedição está parada."], ["Operações e Logística"]),
    ("Impressão", "N1", "requisição", [("P4", 1)],
     ["Instalar impressora no meu notebook", "Adicionar impressora da {l}", "Configurar impressora"],
     ["Preciso instalar a impressora da {l} no meu notebook.",
      "Mudei de sala e quero adicionar a impressora nova no meu computador.",
      "Podem configurar a impressora colorida no meu equipamento?"], None),
    ("Impressão", "N1", "requisição", [("P4", 1)],
     ["Trocar toner", "Toner acabando", "Suprimentos da impressora"],
     ["O toner da impressora da {l} está no fim. Podem providenciar a troca?",
      "Precisamos de mais um pacote de papel e de um toner para a {l}.",
      "Aviso de toner baixo na impressora do setor."], None),
    ("Impressão", "N1", "incidente", [("P3", 1)],
     ["Digitalizar para e-mail não funciona", "Scanner da impressora", "Escaneamento falhando"],
     ["A opção de digitalizar para e-mail na impressora da {l} dá erro.",
      "Escaneio o documento, mas ele não chega no meu e-mail.",
      "O scanner da multifuncional não reconhece o documento e fica travado."], None),
    # ----- Segurança
    ("Segurança", "Segurança", "incidente", [("P3", 1)],
     ["E-mail suspeito (phishing)", "Mensagem estranha pedindo senha", "Possível golpe por e-mail"],
     ["Recebi um e-mail dizendo que meu bônus estava disponível e pedindo para confirmar a senha. Não cliquei.",
      "Chegou uma mensagem com um anexo estranho, supostamente de um fornecedor. Parece golpe.",
      "O e-mail diz ser da TI e pede que eu atualize a senha em um link. Estou reportando."], None),
    ("Segurança", "Segurança", "incidente", [("P2", 1)],
     ["Cliquei em link suspeito", "Abri anexo desconhecido", "Possível infecção após clicar em e-mail"],
     ["Cliquei em um link de um e-mail estranho e depois a página pediu minha senha. Informei e agora estou preocupado.",
      "Abri um anexo de um e-mail que parecia legítimo e o notebook ficou estranho. Já desconectei a rede.",
      "Acredito que caí em um golpe: digitei meu usuário e senha em um site falso."], None),
    ("Segurança", "Segurança", "incidente", [("P2", 1)],
     ["Suspeita de acesso indevido", "Login estranho na minha conta", "Atividade suspeita"],
     ["Recebi aviso de login na minha conta de um local que não conheço. Não fui eu.",
      "Meu e-mail enviou mensagens que eu não escrevi. Acho que minha conta foi invadida.",
      "Aparecem acessos ao BrisaERP no meu usuário em horários em que eu não estava trabalhando."], None),
    ("Segurança", "Segurança", "incidente", [("P2", 1)],
     ["Notebook perdido", "Equipamento roubado", "Perda de celular corporativo"],
     ["Meu notebook foi roubado do carro ontem à noite. Já fiz o boletim de ocorrência.",
      "Perdi o celular corporativo em uma viagem. Ele tem acesso ao e-mail da empresa.",
      "Esqueci a mochila com o notebook em um táxi e não consegui recuperar."], None),
    ("Segurança", "Segurança", "incidente", [("P1", 1)],
     ["Arquivos criptografados", "Suspeita de ransomware", "Arquivos não abrem e pedem resgate"],
     ["Vários arquivos da minha pasta não abrem e apareceu uma mensagem pedindo pagamento para liberar. Desconectei o cabo de rede.",
      "Tela com mensagem de resgate no servidor de arquivos do setor. Todos os documentos ficaram com extensão estranha.",
      "Arquivos de planilha estão sendo renomeados sozinhos e criptografados, em vários computadores."], None),
    ("Segurança", "Segurança", "requisição", [("P4", 1)],
     ["Revisão de permissões", "Dúvida sobre classificação de documento", "Solicito revisão de acessos"],
     ["Gostaria de uma revisão das permissões da minha equipe nas pastas do BrisaDocs.",
      "Tenho dúvida se uma planilha com preços deve ser classificada como Confidencial. Podem orientar?",
      "Solicito revisão dos acessos de um colaborador que mudou de área."], ["Compliance e Jurídico", "Pessoas e Cultura", "Financeiro e Controladoria"]),
    ("Segurança", "Segurança", "incidente", [("P3", 1)],
     ["Pen drive encontrado", "Dispositivo desconhecido", "Pen drive suspeito no estacionamento"],
     ["Encontrei um pen drive no estacionamento. Não conectei em nenhum equipamento e entreguei na portaria.",
      "Um visitante tentou conectar um dispositivo pessoal em um computador do setor. Barrei, mas aviso por precaução.",
      "Há um pen drive desconhecido plugado em um computador compartilhado da expedição."], ["Operações e Logística", "Comercial"]),
]

IMPACTO_ALTO = ["Isso está impedindo a equipe inteira de trabalhar e não temos alternativa.", "Estamos sem como contornar e o time todo está parado.",
                "Não há outra forma de fazer, o setor está bloqueado."]
IMPACTO_BAIXO = ["Consigo trabalhar por outro caminho por enquanto, então não é crítico.", "Tenho uma alternativa provisória, sem pressa.",
                 "Não é bloqueante, mas gostaria de resolver nos próximos dias."]
SAUDACOES = ["Bom dia!", "Boa tarde!", "Olá!", "Olá, pessoal da TI!", "Oi!", "Bom dia, time!", "Prezados.", "Boa tarde, pessoal!", "Pessoal, tudo bem?"]
EXTRAS_REQ = ["Fico no aguardo.", "A aprovação do gestor já está combinada.", "Não há pressa, mas gostaria de ter até o fim da semana.",
              "Posso retirar na TI se for mais fácil.", "Qualquer coisa me chamem no BrisaChat.", "Se precisarem de mais informações, é só avisar."]
FECHAMENTOS = ["Obrigado.", "Obrigada!", "Att.", "Desde já agradeço.", "Aguardo retorno.", "Grato.", "Abs.", "Valeu!"]
EXTRAS = [
    "Já reiniciei o equipamento e o problema continua.", "Isso começou ontem à tarde.", "Outro colega da minha sala tem o mesmo problema.",
    "Não mudei nada nas configurações.", "Posso receber a TI na minha mesa a qualquer hora.", "Já tentei de outro computador e o resultado foi o mesmo.",
    "Estou na unidade de Uberlândia.", "Estou na unidade de Campinas.", "Tenho uma entrega importante hoje e preciso disso resolvido.",
    "Posso ser contatado pelo ramal ou pelo BrisaChat.", "Em anexo envio uma imagem do erro.", "Aconteceu logo depois da atualização de ontem.",
]
FRUSTRADO_ABRE = ["De novo isso!", "Já é a terceira vez que abro esse chamado.", "Isso é inaceitável.", "Estou há dois dias sem conseguir trabalhar por causa disso.",
                  "Já abri chamado antes e ninguém resolveu.", "Ninguém me dá retorno.", "Que descaso.", "Sinceramente, não aguento mais esse problema."]
FRUSTRADO_FECHA = ["Resolvam isso logo, por favor!!", "Já estou perdendo a paciência.", "Isso atrapalha demais o meu trabalho.",
                   "Espero que desta vez resolvam de verdade.", "Estou muito insatisfeito com o suporte.", "Um absurdo ter que pedir de novo."]
URGENTE_ABRE = ["URGENTE:", "Urgente!", "Preciso disso agora.", "Isso está parando a operação!", "Cliente esperando, é urgente."]
POSITIVO = ["Agradeço o excelente atendimento de sempre!", "Obrigado desde já, vocês são sempre muito rápidos.",
            "Muito obrigado pela atenção, o suporte de vocês é nota 10.", "Valeu pela ajuda da última vez, foi ótimo!", "Adoro o jeito que vocês resolvem as coisas, parabéns à equipe."]
ABREV = [(r"\bvocê\b", "vc"), (r"\bpor que\b", "pq"), (r"\bporque\b", "pq"), (r"\btambém\b", "tb"), (r"\bpara\b", "pra"),
         (r"\bhoje\b", "hj"), (r"\bestá\b", "tá"), (r"\bestou\b", "tô"), (r"\bmuito\b", "mt"), (r"\bnão\b", "n"), (r"\bmesmo\b", "msm")]
SENT_POR_PRIO = {"P1": [("urgente", 0.55), ("frustrado", 0.30), ("neutro", 0.15)],
                 "P2": [("urgente", 0.25), ("frustrado", 0.25), ("neutro", 0.45), ("positivo", 0.05)],
                 "P3": [("neutro", 0.62), ("frustrado", 0.17), ("positivo", 0.15), ("urgente", 0.06)],
                 "P4": [("neutro", 0.70), ("positivo", 0.20), ("frustrado", 0.07), ("urgente", 0.03)]}


def pesado(rng, opcoes):
    r, acc = rng.random() * sum(p for _, p in opcoes), 0
    for v, p in opcoes:
        acc += p
        if r <= acc:
            return v
    return opcoes[-1][0]


def aplica_abrev(txt, rng):
    import re
    for a, b in ABREV:
        if rng.random() < 0.8:
            txt = re.sub(a, b, txt, flags=re.I)
    return txt


def gerar():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"] + 4)
    deps = {d["nome"]: sum(q["qtd"].get("c", 0) + q["qtd"].get("u", 0) for q in ficha["quadro"][d["id"]]) for d in ficha["departamentos"]}
    dep_nomes, dep_pesos = list(deps), list(deps.values())
    # pesos de cenário por prioridade, para obter ~6% P1, 18% P2, 46% P3, 30% P4
    alvo = {"P1": 0.06, "P2": 0.18, "P3": 0.46, "P4": 0.30}
    por_prio = {p: [c for c in CENARIOS if any(pr == p for pr, _ in c[3])] for p in alvo}
    ini, fim = dt.date(2026, 1, 5), dt.date(2026, 10, 16)
    dias = [ini + dt.timedelta(days=i) for i in range((fim - ini).days + 1)]
    dias_uteis = [d for d in dias if d.weekday() < 5]
    tickets, vistos = [], set()
    while len(tickets) < N_TICKETS:
        prio_alvo = pesado(rng, list(alvo.items()))
        cen = rng.choice(por_prio[prio_alvo])
        cat, fila, tipo, prios, assuntos, descs, dpref = cen
        prio = prio_alvo
        sent = pesado(rng, SENT_POR_PRIO[prio])
        depto = rng.choice(dpref) if dpref and rng.random() < 0.8 else rng.choices(dep_nomes, weights=dep_pesos)[0]
        slots = {"s": rng.choice(SISTEMAS_ACESSO), "l": rng.choice(LOCAIS), "sw": rng.choice(SOFTWARES), "e": rng.choice(EQUIPS),
                 "m": rng.choice(MOTIVOS_PICO), "n": rng.choice(["3", "4", "5", "seis", "oito"]), "d": depto}
        assunto = rng.choice(assuntos).format(**slots)
        corpo = rng.choice(descs).format(**slots)
        partes = []
        if sent == "frustrado":
            partes.append(rng.choice(FRUSTRADO_ABRE))
        if sent == "urgente" and rng.random() < 0.6:
            partes.append(rng.choice(URGENTE_ABRE))
        partes.append(corpo)
        base = prios[0][0]
        if prio < base:
            partes.append(rng.choice(IMPACTO_ALTO))
        elif prio > base:
            partes.append(rng.choice(IMPACTO_BAIXO))
        comp = rng.random()
        banco = EXTRAS_REQ if tipo == "requisição" else EXTRAS
        if comp > 0.60:  # longo
            partes += rng.sample(banco, rng.choice([2, 3]))
        elif comp > 0.40:
            partes.append(rng.choice(banco))
        if sent == "frustrado":
            partes.append(rng.choice(FRUSTRADO_FECHA))
        if sent == "positivo":
            partes.append(rng.choice(POSITIVO))
        texto = " ".join(partes)
        if comp < 0.15:  # curto: só a primeira frase útil
            texto = " ".join(partes[:2]) if sent in ("frustrado", "urgente") else corpo.split(". ")[0].rstrip(".") + "."
        if sent == "urgente" and rng.random() < 0.5:
            assunto = "[URGENTE] " + assunto
        if rng.random() < 0.7:
            texto = rng.choice(SAUDACOES) + " " + texto
        if rng.random() < 0.45:
            texto = texto + " " + rng.choice(FECHAMENTOS)
        if rng.random() < 0.22:
            texto = aplica_abrev(texto, rng)
            assunto = aplica_abrev(assunto, rng)
        if rng.random() < 0.10:
            texto, assunto = texto.lower(), assunto.lower()
        if rng.random() < 0.06:
            texto = sem_acento(texto)
        if sent == "frustrado" and rng.random() < 0.3:
            texto = texto.replace(".", "!", 1)
        chave = normaliza(assunto + texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        tickets.append({"data": rng.choice(dias_uteis).isoformat(), "departamento_solicitante": depto, "assunto": assunto,
                        "descricao": texto, "categoria": cat, "fila": fila, "prioridade": prio, "tipo": tipo, "sentimento": sent})
    tickets.sort(key=lambda t: t["data"])
    for i, t in enumerate(tickets, 1):
        t["id"] = f"TI-2026-{i:04d}"
    return tickets


def main():
    t = gerar()
    campos = ["id", "data", "departamento_solicitante", "assunto", "descricao", "categoria", "fila", "prioridade", "tipo", "sentimento"]
    escrever_csv("tickets/tickets_ti.csv", campos, t)
    from collections import Counter
    print("tickets:", len(t), dict(Counter(x["prioridade"] for x in t)), dict(Counter(x["sentimento"] for x in t)))


if __name__ == "__main__":
    main()
