function build_table() {
  $.getJSON('results.json', function(results) {
    $.LoadingOverlay("show", {
      background: "white"
    });
    var table = $('<table class="display nowrap cell-border compact" id="results" style="width:100%">');
    var thead = $('<thead>');
    var tfoot = $('<tfoot>');
    var head_row1 = $('<tr>');
    var head_row2 = $('<tr>');
    var foot_row = $('<tr>');
    head_row1.append('<th colspan="2">');
    head_row2.append('<th>&nbsp;</th>','<th>');
    foot_row.append('<th>&nbsp;</th>','<th>');
    var matches = results['matches'];
    for (var i = 0; i < matches.length; ++i) {
      var match_card = $('<th colspan="2">');
      match_card.append('<div>' + matches[i]['team0'] + '</div>');
      match_card.append('<div>' + matches[i]['result'] + '</div>');
      match_card.append('<div>' + matches[i]['team1'] + '</div>');
      head_row1.append(match_card);
      head_row2.append('<th>' + matches[i]['time'] + '</th>');
      head_row2.append('<th>' + matches[i]['round'] + '</th>');
      foot_row.append('<th>' + matches[i]['short_label'] + '</th>');
      foot_row.append('<th>' + matches[i]['round'] + '</th>');
    }
    thead.append(head_row1, head_row2);
    tfoot.append(foot_row);
    var tbody = $('<tbody>');
    var players = results['players'];
    for (var id in players) {
      var p = players[id];
      var tr = $('<tr>');
      tr.append('<th>' + p['name'] + (p['is_queen'] ? ' ♕' : '') + '</th>');
      tr.append('<th class="score"> ' + p['score'] + ' </th>');
      var predictions = p['predictions'];
      for (var i = 0; i < predictions.length; ++i) {
        var res = predictions[i]['result'];
        var score = predictions[i]['score'];
        tr.append('<th>' + ((res == null) ? '-' : res) + '</th>');
        tr.append('<th class="score">' + ((score == null) ? '' : score) + '</th>');
      }
      tbody.append(tr);
    }
    table.append(thead, tbody, tfoot);
    $('body').append(table);
    var draw_handled = false;
    table.on('draw.dt', function() {
      if (!draw_handled) {
        draw_handled = true;
        window.setTimeout(function() {
          document.getElementsByClassName('dataTables_scrollBody')[0].scrollLeft = 10000000;
          $('body').removeClass('hidden');
          $.LoadingOverlay("hide");
        }, 1000);
      }
    }).DataTable({
      paging: false,
      info: false,
      searching: false,
      scrollX: true,
      scrollY: '90vh',
      scrollCollapse: true,
      order: [[1, 'desc']],
      fixedColumns: {
        leftColumns: 2
      }
    });
  });
}
