@Data
@Getter
@Builder
@AllArgsConstructor
@NoArgsConstructor
@EqualsAndHashCode
@JsonInclude(JsonInclude.Include.NON_NULL)
public class WorkItemDescriptor {
    private UUID instanceId;
    private UUID workflowId;
    private String instanceName;
    private String workflowName;
    private List<BoundedParameter> inputs;
    private List<BoundedParameter> outputs;
    private List<BoundedParameter> properties;
    private IoMode inputMode;
    private IoMode outputMode;
}
