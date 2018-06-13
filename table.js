function build_table() {
  $.getJSON('test_results.json', function(results) {
    var table = $('<table class="display nowrap" style="width:100%">');
    var thead = $('<thead>');
    var tfoot = $('<tfoot>');
    var head_row1 = $('<tr>');
    var head_row2 = $('<tr>');
    head_row1.append('<th colspan="2">');
    head_row2.append('<th>','<th>');
    var matches = results['matches'];
    for (var i = 0; i < matches.length; ++i) {
      head_row1.append('<th colspan="2">' + matches[i]['label'] + '</th>');
      head_row2.append('<th>', '<th>');
    }
    thead.append(head_row1, head_row2);
    tfoot.append(head_row2.clone());
    var tbody = $('<tbody>');
    var players = results['players'];
    for (var id in players) {
      var p = players[id];
      var tr = $('<tr>');
      tr.append('<th>' + p['name'] + '</th>');
      tr.append('<th class="score">' + p['score'] + '</th>');
      var predictions = p['predictions'];
      for (var i = 0; i < predictions.length; ++i) {
        var res = predictions[i]['result'];
        var score = predictions[i]['score'];
        tr.append('<th>' + ((res == null) ? '-' : res) + '</th>');
        tr.append('<th class="score">' + ((score == null) ? '' : score) + '</th>');
        tbody.append(tr);
      }
    }
    table.append(thead, tbody, tfoot);
    $('body').append(table);
    table.DataTable({
      paging: false,
      info: false,
      searching: false,
      scrollX: true,
      scrollY: '100vh',
      scrollCollapse: true,
      fixedColumns: {
        leftColumns: 2
      }
    });
    console.log(results['players']);
  });
}
