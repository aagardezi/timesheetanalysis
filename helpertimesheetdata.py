import pandas_gbq
import helpercode

PROJECT_ID = helpercode.get_project_id()

def get_timesheet_data():
    sql = """SELECT * FROM `genaillentsearch.bhtimesheetdemo.TimesheetApprovalHistory` a
            inner join `genaillentsearch.bhtimesheetdemo.BHTimeUsers` b
            on a.TimesheetOwnerEmail = b.EmailAddress"""
    timesheetdf = pandas_gbq.read_gbq(sql, project_id=PROJECT_ID)
    return timesheetdf.to_markdown()


function_handler = {
    "get_timesheet_data": get_timesheet_data
}