function importarDadosDaAPI() {function importarDadosDaAPI() {
  // Define a URL da API  // Define a URL da API
  var url = "https://api.quark.tec.br/rh/ext/v1/frequencias/registro-ponto";  var url = "https://api.quark.tec.br/rh/ext/v1/frequencias/registro-ponto";

  // Define os cabeçalhos da solicitação  // Define os cabeçalhos da solicitação
  var headers = {  var headers = {
    "accept": "*/*",    "accept": "*/*",
    "Auth-token": "4cebd80553d725cbf3157b48e1d56c045423216062ee116652b45087a371ea19",    "Auth-token": "4cebd80553d725cbf3157b48e1d56c045423216062ee116652b45087a371ea19",
    "Unidade-Id": "2981000"    "Unidade-Id": "2981000"
  };  };

  // Define as opções para a solicitação  // Define as opções para a solicitação
  var options = {  var options = {
    "method" : "GET",    "method" : "GET",
    "headers": headers,    "headers": headers,
    "muteHttpExceptions": true    "muteHttpExceptions": true
  };  };

  // Faz a solicitação para a API usando o UrlFetchApp  // Faz a solicitação para a API usando o UrlFetchApp
  try {  try {
    var response = UrlFetchApp.fetch(url, options);    var response = UrlFetchApp.fetch(url, options);

    // Verifica se a resposta da API foi bem-sucedida    // Verifica se a resposta da API foi bem-sucedida
    if (response.getResponseCode() == 200) {    if (response.getResponseCode() == 200) {
      // Se a resposta foi bem-sucedida, obtém os dados      // Se a resposta foi bem-sucedida, obtém os dados
      var responseData = JSON.parse(response.getContentText());      var responseData = JSON.parse(response.getContentText());

      // Processa e insere os dados na planilha do Google Sheets      // Processa e insere os dados na planilha do Google Sheets
      inserirDadosNaPlanilha(responseData);      inserirDadosNaPlanilha(responseData);
      Logger.log("Dados importados com sucesso.");      Logger.log("Dados importados com sucesso.");
    } else {    } else {
      // Se a resposta não foi bem-sucedida, registra uma mensagem de erro      // Se a resposta não foi bem-sucedida, registra uma mensagem de erro
      Logger.log("Erro ao obter dados da API. Código de resposta: " + response.getResponseCode());      Logger.log("Erro ao obter dados da API. Código de resposta: " + response.getResponseCode());
      Logger.log("Resposta: " + response.getContentText());      Logger.log("Resposta: " + response.getContentText());
    }    }
  } catch (error) {  } catch (error) {
    // Registra detalhes sobre o erro ocorrido    // Registra detalhes sobre o erro ocorrido
    Logger.log("Erro ao fazer solicitação à API: " + error);    Logger.log("Erro ao fazer solicitação à API: " + error);
  }  }
}}

// Função para inserir os dados na planilha do Google Sheets// Função para inserir os dados na planilha do Google Sheets
function inserirDadosNaPlanilha(data) {function inserirDadosNaPlanilha(data) {
  // Obtém a planilha ativa e a aba na qual deseja inserir os dados  // Obtém a planilha ativa e a aba na qual deseja inserir os dados
  var planilha = SpreadsheetApp.getActiveSpreadsheet();  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var aba = planilha.getSheetByName("QuarkRH_Daniele"); // Substitua pelo nome da aba desejada  var aba = planilha.getSheetByName("QuarkRH_Daniele"); // Substitua pelo nome da aba desejada

  // Obtém a célula inicial onde os dados serão inseridos  // Obtém a célula inicial onde os dados serão inseridos
  var celulaInicial = aba.getRange("A1"); // Substitua pela célula onde deseja iniciar a inserção dos dados  var celulaInicial = aba.getRange("A1"); // Substitua pela célula onde deseja iniciar a inserção dos dados

  // Limpa o conteúdo da aba antes de inserir os novos dados  // Limpa o conteúdo da aba antes de inserir os novos dados
  aba.clear({contentsOnly: true});  aba.clear({contentsOnly: true});

  // Inserir os dados na planilha  // Inserir os dados na planilha
  for (var i = 0; i < data.length; i++) {  for (var i = 0; i < data.length; i++) {
    var rowData = data[i];    var rowData = data[i];
    for (var key in rowData) {                          for (var key in rowData) {
      if (rowData.hasOwnProperty(key)) {      if (rowData.hasOwnProperty(key)) {
        celulaInicial.offset(i, 0).setValue(key);        celulaInicial.offset(i, 0).setValue(key);
        celulaInicial.offset(i, 1).setValue(rowData[key]);        celulaInicial.offset(i, 1).setValue(rowData[key]);
      }      }
    }    }
  }  }
  Logger.log("Dados inseridos na planilha.");  Logger.log("Dados inseridos na planilha.");
}}
function importarDadosDaAPI() {
  // Define a URL da API
  var url = "https://api.quark.tec.br/rh/ext/v1/frequencias/registro-ponto";

  // Define os cabeçalhos da solicitação
  var headers = {
    "accept": "*/*",
    "Auth-token": "4cebd80553d725cbf3157b48e1d56c045423216062ee116652b45087a371ea19",
    "Unidade-Id": "2981000"
  };

  // Define as opções para a solicitação
  var options = {
    "method" : "GET",
    "headers": headers,
    "muteHttpExceptions": true
  };

  // Faz a solicitação para a API usando o UrlFetchApp
  try {
    var response = UrlFetchApp.fetch(url, options);

    // Verifica se a resposta da API foi bem-sucedida
    if (response.getResponseCode() == 200) {
      // Se a resposta foi bem-sucedida, obtém os dados
      var responseData = JSON.parse(response.getContentText());

      // Processa e insere os dados na planilha do Google Sheets
      inserirDadosNaPlanilha(responseData);
      Logger.log("Dados importados com sucesso.");
    } else {
      // Se a resposta não foi bem-sucedida, registra uma mensagem de erro
      Logger.log("Erro ao obter dados da API. Código de resposta: " + response.getResponseCode());
      Logger.log("Resposta: " + response.getContentText());
    }
  } catch (error) {
    // Registra detalhes sobre o erro ocorrido
    Logger.log("Erro ao fazer solicitação à API: " + error);
  }
}

// Função para inserir os dados na planilha do Google Sheets
function inserirDadosNaPlanilha(data) {
  // Obtém a planilha ativa e a aba na qual deseja inserir os dados
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var aba = planilha.getSheetByName("QuarkRH_Daniele"); // Substitua pelo nome da aba desejada

  // Obtém a célula inicial onde os dados serão inseridos
  var celulaInicial = aba.getRange("A1"); // Substitua pela célula onde deseja iniciar a inserção dos dados

  // Limpa o conteúdo da aba antes de inserir os novos dados
  aba.clear({contentsOnly: true});

  // Inserir os dados na planilha
  for (var i = 0; i < data.length; i++) {
    var rowData = data[i];
    for (var key in rowData) {
      if (rowData.hasOwnProperty(key)) {
        celulaInicial.offset(i, 0).setValue(key);
        celulaInicial.offset(i, 1).setValue(rowData[key]);
      }
    }
  }
  Logger.log("Dados inseridos na planilha.");
}