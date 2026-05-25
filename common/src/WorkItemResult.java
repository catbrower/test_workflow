package brower.finance.optimizer.common.model.work;

import brower.finance.optimizer.common.constants.work.WorkOutcome;
import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class WorkItemResult {

    public static WorkItemResult success() {
        return new WorkItemResult(WorkOutcome.SUCCESS, null, null);
    }

    public static WorkItemResult success(List<Parameter> values) {
        return new WorkItemResult(WorkOutcome.SUCCESS, null, values);
    }

    public static WorkItemResult failure(String error) {
        return new WorkItemResult(WorkOutcome.FAILURE, error, null);
    }

    private WorkOutcome outcome;
    private String error;
    private List<Parameter> values;

    public WorkItemResult(WorkOutcome outcome, String error, List<Parameter> values) {
        this.outcome = outcome;
        this.error = error;
        this.values = values;
    }
}
