# 🌐 ICMPMASTER — Preditor de Qualidade da Rede

O **ICMPMASTER** é um sistema de monitoramento e análise da qualidade de redes, desenvolvido em Python, que utiliza técnicas de **Machine Learning** para identificar comportamentos de rede e auxiliar na antecipação de possíveis problemas de conectividade.

O projeto integra a coleta de medições reais por meio do **RIPE Atlas**, o processamento de métricas de rede, um modelo de classificação baseado em **Árvore de Decisão** e uma interface interativa desenvolvida com **Streamlit**.

Além do monitoramento de redes, o sistema disponibiliza um simulador de eventos para analisar diferentes condições de conectividade em um ambiente controlado.

---

## 🎯 Objetivo

Desenvolver uma aplicação capaz de coletar, processar e analisar métricas de conectividade, utilizando aprendizado de máquina para auxiliar na identificação de possíveis degradações na qualidade da rede.

O sistema busca:

- Monitorar métricas de conectividade de diferentes fluxos de rede.
- Processar medições obtidas por meio do RIPE Atlas.
- Identificar padrões associados à estabilidade e à degradação da conexão.
- Utilizar uma Árvore de Decisão para gerar classificações e previsões.
- Disponibilizar informações em dashboards interativos.
- Permitir a simulação de diferentes condições de rede.
- Automatizar a coleta e a atualização das informações monitoradas.

---

## 🧠 Tecnologias utilizadas

| Tecnologia | Aplicação |
|---|---|
| Python 3.11 | Linguagem principal do projeto |
| Scikit-learn 1.9.1 | Modelo de Machine Learning |
| Pandas | Manipulação e processamento de dados |
| NumPy | Operações numéricas |
| Streamlit | Desenvolvimento da interface web |
| Plotly | Visualização interativa de dados |
| Joblib | Serialização e carregamento do modelo |
| RIPE Atlas | Fonte de medições reais de conectividade |
| Git e GitHub | Versionamento e colaboração |

---

## ⚙️ Funcionamento do sistema

O ICMPMASTER possui uma arquitetura que integra coleta, processamento, classificação e visualização de dados.

O funcionamento geral ocorre em cinco etapas:

**1. Coleta de dados**

O sistema consulta medições disponibilizadas pelo RIPE Atlas, obtendo informações relacionadas à conectividade dos fluxos monitorados.

**2. Processamento**

As medições são organizadas e transformadas em atributos utilizados pelo modelo de Machine Learning.

**3. Classificação e previsão**

A Árvore de Decisão analisa os atributos processados e produz previsões de acordo com as regras aprendidas durante seu treinamento.

**4. Armazenamento**

Os resultados do monitoramento são registrados em arquivos CSV, permitindo consultas e análises posteriores.

**5. Visualização**

Os dados são apresentados em dashboards interativos, permitindo acompanhar o comportamento da rede e os resultados das previsões.

### Fluxo de funcionamento

```text
             RIPE Atlas
                 |
                 v
         Coleta automática
                 |
                 v
      Processamento dos dados
                 |
                 v
        Árvore de Decisão
                 |
                 v
       Classificação e previsão
                 |
          +------+------+
          |             |
          v             v
     Arquivos CSV    Streamlit
                        |
                        v
                Dashboard interativo
```

---

## 📊 Funcionalidades

### 1. Dashboard histórico

O dashboard histórico permite consultar e analisar os dados coletados durante o desenvolvimento do projeto.

Por meio da interface, é possível visualizar informações sobre o comportamento dos fluxos de rede, métricas de conectividade e resultados das análises realizadas.

Essa funcionalidade auxilia na compreensão do comportamento histórico da rede.

### 2. Monitoramento automático

O ICMPMASTER possui um módulo de monitoramento que consulta periodicamente o RIPE Atlas.

O sistema permite:

- Consultar novas medições de conectividade.
- Processar automaticamente os dados recebidos.
- Executar previsões utilizando o modelo de Machine Learning.
- Armazenar os resultados obtidos.
- Atualizar as informações apresentadas no dashboard.
- Acompanhar o comportamento dos fluxos monitorados.

O monitoramento depende da disponibilidade das medições na API do RIPE Atlas. Portanto, a atualização da interface não significa necessariamente que uma nova medição foi disponibilizada.

### 3. Simulador de eventos

O sistema disponibiliza um simulador para testar diferentes condições de conectividade sem a necessidade de provocar alterações em uma rede real.

Os cenários disponíveis são:

| Cenário | Descrição |
|---|---|
| 🟢 OK | Representa condições de conectividade estáveis |
| 🟡 RISCO | Representa situações de possível degradação |
| 🔴 FALHA | Representa condições críticas de conectividade |

O simulador gera medições artificiais, processa os dados e permite observar o comportamento das previsões.

**Importante:** os cenários representam condições simuladas. A classificação produzida pelo modelo pode ser diferente do cenário selecionado, pois depende dos atributos analisados.

### 4. Modelo de Machine Learning

O ICMPMASTER utiliza um modelo baseado no algoritmo **Decision Tree Classifier**, da biblioteca Scikit-learn.

Uma Árvore de Decisão realiza classificações por meio de regras construídas durante o treinamento.

No contexto do projeto, o modelo utiliza atributos derivados das medições de conectividade para analisar o comportamento dos fluxos monitorados.

O modelo original é preservado durante a execução da aplicação, sem necessidade de realizar um novo treinamento.

---

## 📁 Estrutura do projeto

A organização principal do ICMPMASTER é apresentada abaixo:

```text
icmpmaster/
│
├── app.py
│
├── modelo_icmp.py
├── monitoramento_icmp.py
├── simulador_icmp.py
├── experimento_sintetico.py
├── empacotar_modelo.py
├── contrato_icmp.py
│
├── config/
│   ├── coleta.py
│   └── coleta_config.json
│
├── data/
│   ├── interim/
│   └── processed/
│
├── pages/
│   ├── 2_Monitoramento_automatico.py
│   └── 3_Simulador_de_eventos.py
│
├── pacote_modelo/
│   ├── modelo.joblib
│   ├── metadados.json
│   └── baseline.csv
│
├── resultados_sinteticos/
│
├── tests/
│   └── test_integracao.py
│
├── documentos/
│   ├── Diagramas/
│   └── notebooks/
│
├── requirements.txt
│
└── README.md
```

**Observação:** a estrutura apresenta os principais arquivos e diretórios do projeto, sem listar todos os arquivos de dados e artefatos intermediários.

---

## 🚀 Instalação e execução

### Pré-requisitos

Para executar o ICMPMASTER, recomenda-se:

- Python 3.11;
- Git;
- Visual Studio Code ou outro editor de código;
- Conexão com a internet para consultar o RIPE Atlas.

### 1. Clonar o repositório

```powershell
git clone https://github.com/HenriqueUBC/icmpmaster.git
```

Acesse o diretório:

```powershell
cd icmpmaster
```

### 2. Criar um ambiente virtual

No PowerShell:

```powershell
py -m venv .venv
```

### 3. Instalar as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O ambiente virtual permite isolar as bibliotecas utilizadas pelo projeto.

### 4. Iniciar a aplicação

Execute:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

O Streamlit disponibilizará um endereço local para acessar a interface pelo navegador.

A partir da aplicação principal, é possível navegar pelas páginas disponíveis.

---

## 🌐 Executando o monitoramento automático

Para utilizar o monitoramento completo, é necessário manter a interface Streamlit e o processo de coleta em execução.

### Terminal 1 — Interface Streamlit

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Terminal 2 — Monitoramento

Abra outro terminal na pasta do projeto e execute:

```powershell
.\.venv\Scripts\python.exe monitoramento_icmp.py
```

O processo de monitoramento realiza consultas periódicas às medições do RIPE Atlas.

Enquanto isso, o Streamlit permite acompanhar as informações processadas.

**Atenção:** o monitoramento depende da disponibilidade da API e das medições das sondas utilizadas. A aplicação não garante a chegada de novas medições em intervalos exatos.

---

## 🧪 Executando o simulador

O simulador permite gerar eventos artificiais para avaliar o comportamento do sistema em diferentes condições.

Para executar o cenário **OK**:

```powershell
.\.venv\Scripts\python.exe simulador_icmp.py --cenario OK
```

Para executar o cenário **RISCO**:

```powershell
.\.venv\Scripts\python.exe simulador_icmp.py --cenario RISCO
```

Para executar o cenário **FALHA**:

```powershell
.\.venv\Scripts\python.exe simulador_icmp.py --cenario FALHA
```

Também é possível acessar a página **Simulador de eventos** pela interface Streamlit.

Os dados gerados são sintéticos e não representam medições reais da rede.

---

## 🔬 Experimento com dados sintéticos

O projeto possui um experimento independente que utiliza dados artificiais para avaliar o comportamento de um modelo em condições controladas.

Para executar:

```powershell
.\.venv\Scripts\python.exe experimento_sintetico.py
```

Os resultados são armazenados no diretório:

```text
resultados_sinteticos/
```

Esse experimento utiliza um modelo treinado separadamente com dados artificiais e **não modifica a Árvore de Decisão original do ICMPMASTER**.

Os resultados devem ser interpretados considerando as características e limitações dos dados simulados.

---

## 📦 Empacotamento do modelo

O projeto disponibiliza um script responsável por gerar um pacote com o modelo e os arquivos necessários à sua utilização.

Para executar:

```powershell
.\.venv\Scripts\python.exe empacotar_modelo.py
```

O procedimento:

1. Carrega a Árvore de Decisão original.
2. Organiza os arquivos necessários ao pacote.
3. Registra os metadados do modelo.
4. Verifica a compatibilidade dos atributos.
5. Compara as previsões do modelo original e do modelo empacotado.

O processo não realiza um novo treinamento da árvore original.

---

## ✅ Testes e validação

O ICMPMASTER possui testes automatizados para verificar componentes essenciais do sistema.

Para executá-los:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Resultados da validação

Na validação realizada em novembro de 2026, utilizando Python 3.11.9 e Scikit-learn 1.9.1, foram obtidos os seguintes resultados:

| Verificação | Resultado |
|---|---|
| Carregamento da árvore original | Aprovado |
| Independência de componentes em relação ao Streamlit | Aprovado |
| Preparação de dados para classificação | Aprovado |
| Contrato de entrada e separação de rótulos | Aprovado |
| Validação de endereços IP | Aprovado |
| Tratamento de timeout | Aprovado |
| Independência do experimento sintético | Aprovado |
| Reprodutibilidade do simulador | Aprovado |
| Execução dos três cenários simulados | Aprovado |

**Resultado geral: 9 testes executados e 9 aprovados.**

### Validação operacional

Além dos testes automatizados, foi realizada uma verificação funcional do monitoramento.

Durante a execução, foram observados:

- Inicialização do coletor sem erros reportados.
- Atualização automática da interface.
- Recebimento de medições reais.
- Exibição de previsões.
- Atualização dos arquivos CSV utilizados pelo monitoramento.

Esses resultados demonstram o funcionamento básico da integração entre os componentes, mas não substituem testes prolongados de estabilidade e desempenho.

---

## ⚠️ Limitações

O ICMPMASTER é um projeto acadêmico desenvolvido para fins de estudo, experimentação e demonstração de técnicas de monitoramento de redes e Machine Learning.

Algumas limitações devem ser consideradas:

- A coleta real depende da disponibilidade do RIPE Atlas.
- A atualização da interface não garante a chegada imediata de novas medições.
- As previsões dependem da qualidade e das características dos dados disponíveis.
- O simulador utiliza dados artificiais, que não reproduzem todas as condições de uma rede real.
- Os resultados dos experimentos sintéticos não devem ser interpretados como desempenho do modelo original em produção.
- O sistema não substitui ferramentas profissionais de monitoramento e diagnóstico de redes.

---

## 👨‍💻 Integrantes do grupo

Projeto desenvolvido por:

- **Eduardo Quintino Filho**
- **Felipe Veiga da Silva**
- **Henrique de Aguiar Fernandes**
- **Niccolas Lupetti dos Santos**
- **Tharik Lima da Silva**

---

## 🎓 Contexto acadêmico

O ICMPMASTER foi desenvolvido como projeto acadêmico, integrando conhecimentos de:

- Redes de computadores;
- Programação em Python;
- Ciência de dados;
- Aprendizado de máquina;
- Engenharia de software;
- Desenvolvimento de interfaces interativas;
- Testes e integração de sistemas.

O projeto demonstra a aplicação prática dessas tecnologias em um sistema de análise e monitoramento da qualidade de redes.

---

**ICMPMASTER — Monitoramento, análise e previsão da qualidade da rede.**