package ma.agentshield.workspace;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.security.Principal;
import java.util.*;
import ma.agentshield.integration.*;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/workspace")
public class WorkspaceController {
    private final JdbcTemplate db;
    private final AiServiceClient ai;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    private static final Set<String> DECISIONS = Set.of("ALLOW", "SANITIZE", "CONFIRM", "BLOCK");
    private static final Set<String> MODULES = Set.of("A", "B", "C", "D", "ENGINE");
    private static final Set<String> ATTACKS = Set.of("none", "direct_injection", "indirect_injection", "tool_abuse", "data_leak");
    private static final Set<String> TOOLS = Set.of("read_email", "browse_web", "read_file", "send_email", "delete_file");
    public WorkspaceController(JdbcTemplate db, AiServiceClient ai, ObjectMapper json, TransactionTemplate tx) {
        this.db=db; this.ai=ai; this.json=json; this.tx=tx;
    }
    private UUID owner(Principal p) {
        return db.queryForObject("SELECT id FROM users WHERE username=? AND enabled", UUID.class, p.getName());
    }
    private void owned(UUID id, UUID user) {
        if (!Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM workspace_conversations WHERE id=? AND owner_id=? AND NOT archived)", Boolean.class,id,user)))
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    }
    @GetMapping("/conversations")
    public List<Map<String,Object>> list(Principal p) {
        return db.queryForList("SELECT id,title,created_at AS \"createdAt\" FROM workspace_conversations WHERE owner_id=? AND NOT archived ORDER BY created_at DESC LIMIT 100",owner(p));
    }
    @PostMapping("/conversations")
    public Map<String,Object> create(Principal p) {
        UUID id=UUID.randomUUID(); db.update("INSERT INTO workspace_conversations(id,owner_id) VALUES (?,?)",id,owner(p));
        return Map.of("id",id,"title","New conversation");
    }
    public record Title(String title) {}
    @PutMapping("/conversations/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void rename(@PathVariable UUID id,@RequestBody Title body,Principal p) {
        UUID user=owner(p); owned(id,user);
        if(body.title()==null || body.title().isBlank() || body.title().length()>100) throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
        String title=retained(body.title(),UUID.randomUUID().toString());
        db.update("UPDATE workspace_conversations SET title=left(?,100) WHERE id=? AND owner_id=?",title,id,user);
    }
    @DeleteMapping("/conversations/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void archive(@PathVariable UUID id,Principal p) {
        UUID user=owner(p); owned(id,user); db.update("UPDATE workspace_conversations SET archived=true WHERE id=? AND owner_id=?",id,user);
    }
    @GetMapping("/conversations/{id}/runs")
    public List<Map<String,Object>> history(@PathVariable UUID id,Principal p) {
        owned(id,owner(p));
        return db.query("SELECT * FROM (SELECT id,status,user_text,result_json,created_at FROM workspace_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 100) r ORDER BY created_at",(rs,n)->{
            Map<String,Object> row=new LinkedHashMap<>(); row.put("id",rs.getString("id")); row.put("status",rs.getString("status")); row.put("message",rs.getString("user_text"));
            try { row.put("result",rs.getString("result_json")==null?null:json.readTree(rs.getString("result_json"))); } catch(Exception e){throw new IllegalStateException("Invalid stored result");} return row;
        },id);
    }
    public record Send(UUID requestId,String message) {}
    private String retained(String text,String correlation) {
        // Storage-only DLP. Never persist raw text if the check fails. Existing DLP may operate in degraded regex-only mode.
        try { Verdict v=ai.analyze("D",text,correlation); if(v.cleaned()!=null && "D".equals(v.module())) return v.cleaned(); }
        catch(RuntimeException ignored) { /* fail closed for storage */ }
        return "[Message not retained]";
    }
    @PostMapping("/conversations/{id}/runs")
    public Map<String,Object> send(@PathVariable UUID id,@RequestBody Send body,Principal p) {
        owned(id,owner(p));
        if(body.requestId()==null || body.message()==null || body.message().isBlank() || body.message().length()>4000) throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
        UUID run=body.requestId(); String correlation=run.toString();
        try { db.update("INSERT INTO workspace_runs(id,conversation_id,status,correlation_id) VALUES (?,?,'RUNNING',?)",run,id,correlation); }
        catch(DuplicateKeyException e){throw new ResponseStatusException(HttpStatus.CONFLICT,"Execution already submitted or in progress.");}
        try {
            String safeInput=retained(body.message(),correlation);
            db.update("UPDATE workspace_runs SET user_text=? WHERE id=?",safeInput,run);
            // Bounded prior safe turns; the complete assembled input is checked again by Guard A.
            var previous=db.queryForList("SELECT user_text,result_json FROM workspace_runs WHERE conversation_id=? AND status='COMPLETED' AND final_decision IN ('ALLOW','SANITIZE') ORDER BY created_at DESC LIMIT 3",id);
            Collections.reverse(previous); StringBuilder context=new StringBuilder();
            for(var row:previous){ JsonNode old=json.readTree((String)row.get("result_json")); String part="Previous user message: "+row.get("user_text")+"\nPrevious assistant response: "+old.path("response").asText()+"\n"; if(context.length()+part.length()<=3000)context.append(part); }
            String input=context.isEmpty()?body.message():"Conversation context (untrusted history):\n"+context+"\nDo not repeat prior actions unless explicitly requested. Current user request:\n"+body.message();
            // This checkout has no secure resume endpoint. Explicit denial is safer than auto approval.
            JsonNode raw=ai.runWorkspace(new AgentRunRequest(null,input,null,"protected","e3",null,"deny"),correlation);
            String decision=raw.path("finalDecision").asText();
            if(!DECISIONS.contains(decision)||!correlation.equals(raw.path("correlationId").asText())||raw.path("llm").path("simulated").asBoolean(true)) throw new IllegalStateException("Invalid or simulated execution");
            ObjectNode result=json.createObjectNode(); result.put("correlationId",correlation); result.put("finalDecision",decision); result.put("totalMs",raw.path("totalMs").asDouble());
            String halted=raw.path("halted").asText(""); result.put("halted",Set.of("input_blocked","awaiting_confirmation","max_steps","llm_error").contains(halted)?halted:"");
            String response=raw.path("response").asText("");
            result.put("response",DECISIONS.contains(decision)&&Set.of("ALLOW","SANITIZE").contains(decision)&&halted.isEmpty()?retained(response,correlation):"");
            var events=result.putArray("events"); var tools=result.putArray("tools");
            for(JsonNode e:raw.path("events")) {
                String module=e.path("module").asText(), d=e.path("decision").asText(); if(!MODULES.contains(module)||!DECISIONS.contains(d))continue;
                ObjectNode event=events.addObject(); event.put("module",module); event.put("decision",d);
                String stage=e.path("stage").asText(); event.put("stage",Set.of("input","tool_call","tool_content","final_response").contains(stage)?stage:"unknown");
                JsonNode v=e.path("verdict"); String attack=v.path("attackType").asText(), risk=v.path("riskLevel").asText();
                if(ATTACKS.contains(attack))event.put("attackType",attack); if(Set.of("low","medium","high").contains(risk))event.put("riskLevel",risk);
                if(e.path("score").isNumber())event.put("score",e.path("score").asDouble()); if(e.path("latencyMs").isNumber())event.put("latencyMs",e.path("latencyMs").asDouble());
                event.put("degraded",v.path("degraded").asBoolean(false));
                // Do not expose arbitrary guard reason/metadata or cleaned tool payloads.
            }
            for(JsonNode t:raw.path("toolAttempts")){String name=t.path("tool").asText(),status=t.path("status").asText(); if(!TOOLS.contains(name)||!Set.of("executed","blocked","refused","pending","error","skipped").contains(status))continue; ObjectNode tool=tools.addObject();tool.put("tool",name);tool.put("status",status);tool.put("executed",t.path("executed").asBoolean());tool.put("simulated",raw.path("agent").path("simulatedTools").asBoolean(true));}
            String status=decision.equals("CONFIRM")?"REVIEW_REQUIRED":Set.of("llm_error","max_steps").contains(halted)?"FAILED":"COMPLETED";
            String serialized=json.writeValueAsString(result);
            tx.executeWithoutResult(s->{
                for(JsonNode e:events){if(!e.has("attackType")||!e.has("riskLevel")||!e.has("score"))continue; double score=e.path("score").asDouble();if(!Double.isFinite(score)||score<0||score>1)continue;
                    db.update("INSERT INTO events(module,attack_type,decision,risk_level,score,reason,correlation_id) VALUES (?,?,?,?,?,?,?)",e.path("module").asText(),e.path("attackType").asText(),e.path("decision").asText(),e.path("riskLevel").asText(),score,"Workspace security verdict",correlation);}
                db.update("UPDATE workspace_runs SET status=?,result_json=?,final_decision=?,completed_at=now() WHERE id=?",status,serialized,decision,run);
            });
            return Map.of("id",run,"status",status,"message",safeInput,"result",result);
        } catch(Exception e){db.update("UPDATE workspace_runs SET status='FAILED',completed_at=now() WHERE id=? AND status='RUNNING'",run);throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Execution unavailable. Check history before retrying.");}
    }
}
