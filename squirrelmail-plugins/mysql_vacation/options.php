<?php
   define('SM_PATH', '../../');

   include_once (SM_PATH . 'include/validate.php');
   include_once (SM_PATH . 'functions/page_header.php');
   include_once (SM_PATH . 'functions/i18n.php');
   include_once (SM_PATH . 'include/load_prefs.php');
   include_once (SM_PATH . 'plugins/mysql_vacation/config.php');
   
   global $vacationMessageSubmit, $messageText, $vacationStatus,
          $username, $data_dir, $color;

   sqgetGlobalVar('vacationMessageSubmit', $vacationMessageSubmit, SQ_POST);

   if (isset($vacationMessageSubmit) && $vacationMessageSubmit == 1)
   {
      sqgetGlobalVar('messageText', $messageText, SQ_POST);
      sqgetGlobalVar('vacationStatus', $vacationStatus, SQ_POST);
      $messageText = charset_encode($messageText, "utf-8");
      if (isset($vacationStatus) && $vacationStatus == 1)
          vacationSet(1, $messageText);
      else
      {
          $vacationStatus = 0;
          vacationSet(0, $messageText);
      }
      $location = '../../src/options.php';
      header('Location: ' . $location);
      exit(0);
   }
   else     
       list($vacationStatus, $messageText) = vacationReadPref();
   $messageText = charset_decode("utf-8", $messageText);

   displayPageHeader($color, 'None', 'document.forms[0].elements["messageText"].focus();');
   echo '<br>';
   echo '<form method="POST"><input type="hidden" name="vacationMessageSubmit" value="1">'
      . '<table width=95% align=center cellpadding=2 cellspacing=2 border=0>'
      . '<tr><td bgcolor="' . $color[0] . '">'
      . '<center><b>'
      . _("Vacation / Autoresponder");
   ?>

      </b></center>
      </td>
   </tr>
   <tr> 
      <td align="center">
         <table width="70%" cellspacing="2">
            <tr>
               <td valign="top">
                  <br>
                  <input type="checkbox" name="vacationStatus" value="1" <?php
                                                   if ($vacationStatus == 1) echo ' CHECKED' ?>>
               </td>
               <td>
                  <br>
                  <b><?php echo _("Activate vacation autoresponder") ?></b>
               </td>
            </tr>
            <tr>
               <td colspan="2"> 
                  <br>
                  <b><?php echo _("Message text"); ?></b>:
                  <br>
                  <textarea name="messageText" rows="5" cols="50" wrap="off"><?php echo $messageText; ?></textarea>
               </td>
            </tr>
            <tr>
               <td align=right colspan="2">
                  <br>
                  <input type="submit" value="<?php echo _("Submit"); ?>">
               </td>
            </tr>
         </table>
      </td>
   </tr>
</table>
</form>
</body>
</html>

<?php

exit(0);


function showError($message)
{
   global $color;
   displayPageHeader($color, 'None');
   echo '<br><br><center><font color="' . $color[2] . '"><b>'
      . $message
      . '</b></font></center></body></html>';
}

function vacationMysqlConnect()
{
   global $vacationDB,
          $mysql_server, $mysql_user, $mysql_pwd, $mysql_database;

   $vacationDB = mysql_connect($mysql_server, $mysql_user, $mysql_pwd);
   if (!$vacationDB) 
   {
      showError('ERROR: Could not connect to database');
      exit(1);
   }
   if (!mysql_select_db($mysql_database, $vacationDB)) 
   {
      showError('ERROR: Could not find database');
      exit(1);
   }
   mysql_query('set names utf8', $vacationDB);
}

function vacationReadPref()
{
    global $username, $vacationDB,
           $mysql_table, $mysql_vacation, $mysql_vacation_text, $mysql_userid;

    vacationMysqlConnect();
    $query_string = "select $mysql_vacation, $mysql_vacation_text from $mysql_table where $mysql_userid  = \"" .
                    mysql_real_escape_string($username) .
                    '"';
    $select_result = mysql_query($query_string, $vacationDB);
    if (!$select_result) 
    {
        showError('ERROR: Database call failed');
        exit(1);
    }
    if (mysql_num_rows($select_result) != 1) 
    {
        showError('ERROR: Could not fetch vacation info');
        exit(1);
    }
    return mysql_fetch_row($select_result);
}

function vacationSet($enable, $msg)
{
    global $username, $vacationDB,
           $mysql_table, $mysql_vacation, $mysql_vacation_text, $mysql_userid;

    vacationMysqlConnect();
    $query_string = "update $mysql_table set $mysql_vacation = $enable" .
                    ", $mysql_vacation_text = \"" . mysql_real_escape_string($msg) . '"' . 
                    " where $mysql_userid  = \"" .
                    mysql_real_escape_string($username) .
                    '"';
    if (!mysql_query($query_string, $vacationDB)) 
    {
        showError('ERROR: Database call failed');
        exit(1);
    }
    /*
    if (mysql_affected_rows($vacationDB) != 1) 
    {
        showError('ERROR: Could not update vacation info: ' . $query_string . ' : '. mysql_affected_rows($vacationDB) .' : '. mysql_error($vacationDB));
        exit(1);
    }
    */
}
?>
